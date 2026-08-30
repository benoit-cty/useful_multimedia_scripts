#!/usr/bin/python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["ffmpeg-python", "click"]
# ///

# Description: Re-encode videos to save space, replacing originals only after verification.
#
# Designed for photo/video archives (e.g. a NAS). Safety features:
#  - the original is only deleted after the encoded file has been verified
#    (video stream present, duration match, full decode check)
#  - --dry-run to list what would be processed without touching anything
#  - --limit N to only encode the first N candidates
#  - --confirm-first N to manually validate the first N replacements
#  - --trash-dir to move originals aside instead of deleting them
#  - videos already encoded by this script (metadata tag) or already in HEVC are skipped
#  - --camera "DMC-G8" to only process videos from a given camera (needs exiftool)
#  - the audio is levelled to -16 LUFS by default, but measured first and left
#    untouched when it is silent (amplifying only hiss) or already on target;
#    -B disables it entirely
#
# Tested under Ubuntu 22.04
# You need FFMPEG :
#  pip install ffmpeg-python ffmpeg-normalize click
# For --camera you need exiftool :
#  sudo apt install libimage-exiftool-perl
#
import os
import re
import sys
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
try:
    import ffmpeg
    import click
except ImportError:
    print("You need to install ffmpeg-python : pip install ffmpeg-python ffmpeg-normalize click")
    sys.exit(1)

from typing import List, Optional, Tuple

FFMPEG_BIN = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mts", ".m2ts", ".avi", ".mpg", ".mpeg", ".wmv", ".3gp", ".mkv"}

# Metadata tag to identify re-encoded videos
ENCODER_TAG = "encoded_by_script"
ENCODER_VALUE = "encode_video.py"

TEMP_PREFIX = ".tmp_encode_"


def human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024 or unit == "TB":
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024


def find_videos(directory, recursive=True):
    """Find all video files in directory, skipping hidden files/dirs and NAS metadata dirs."""
    videos = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs and Synology metadata dirs (@eaDir, #recycle...)
            dirs[:] = sorted(d for d in dirs if not d.startswith((".", "@", "#")))
            for f in sorted(files):
                if f.startswith("."):
                    continue
                if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                    videos.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(directory)):
            path = os.path.join(directory, f)
            if f.startswith(".") or not os.path.isfile(path):
                continue
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                videos.append(path)
    return videos


def get_camera_model(video_file) -> Optional[str]:
    """Read the camera model from the file metadata using exiftool.

    Lumix G80 videos report 'DMC-G80' (or 'DMC-G81'/'DMC-G85' depending on region).
    """
    try:
        result = subprocess.run(
            ["exiftool", "-s3", "-Model", video_file],
            capture_output=True, universal_newlines=True, timeout=60,
        )
        model = result.stdout.strip()
        return model if model else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_nvenc_works(codec="hevc_nvenc") -> Tuple[bool, str]:
    """Encode a tiny test pattern to verify that the NVENC encoder is usable.

    Catches broken CUDA setups (e.g. driver updated without reboot) before
    touching any real file.
    """
    result = subprocess.run(
        [FFMPEG_BIN, "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
         "-c:v", codec, "-f", "null", "-"],
        capture_output=True, universal_newlines=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, "OK"


def is_already_encoded(probe):
    """Check if video was already encoded by this script using its metadata tag"""
    format_tags = probe.get("format", {}).get("tags", {})
    for key, value in format_tags.items():
        if key.lower() == ENCODER_TAG.lower() and value == ENCODER_VALUE:
            return True
    return False


def get_duration(probe) -> Optional[float]:
    try:
        return float(probe["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def verify_encoded_file(original_probe, encoded_file, decode_check=True) -> Tuple[bool, str]:
    """Verify that the encoded file is a valid replacement for the original.

    Checks: readable, has a video stream, duration matches the original,
    and optionally that the whole file decodes without error.
    """
    try:
        probe = ffmpeg.probe(encoded_file)
    except Exception as e:
        return False, f"encoded file is not readable: {e}"

    video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    if not video_streams:
        return False, "encoded file has no video stream"

    original_duration = get_duration(original_probe)
    encoded_duration = get_duration(probe)
    if original_duration is None or encoded_duration is None:
        return False, "could not compare durations"
    tolerance = max(1.5, original_duration * 0.02)
    if abs(original_duration - encoded_duration) > tolerance:
        return False, f"duration mismatch: original={original_duration:.1f}s encoded={encoded_duration:.1f}s"

    if decode_check:
        result = subprocess.run(
            [FFMPEG_BIN, "-v", "error", "-xerror", "-i", encoded_file, "-f", "null", "-"],
            capture_output=True, universal_newlines=True,
        )
        if result.returncode != 0 or result.stderr.strip():
            return False, f"decode check failed: {result.stderr.strip()[:500]}"

    return True, f"OK (duration {encoded_duration:.1f}s)"


def build_encode_command(video_file, output_file, quality, target_height, codec,
                         audio_filter=None, audio_bitrate="128k", gpu_frames=True):
    """Build the ffmpeg command line for one encode.

    gpu_frames=True keeps the decoded frames in VRAM (NVDEC -> scale_cuda ->
    NVENC) instead of copying them back and forth through system memory. Some
    sources cannot be decoded by NVDEC (10-bit H.264 for instance), hence the
    CPU-frames fallback in encode_one_video().
    """
    cmd = [FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
           "-hwaccel", "cuda"]  # GPU decoding, falls back to CPU if unsupported
    if gpu_frames:
        # Keep the frames on the GPU between the decoder and the encoder
        cmd += ["-hwaccel_output_format", "cuda"]
    cmd += ["-i", video_file,
            "-map", "0:v:0", "-map", "0:a?"]

    if target_height:
        # scale_cuda resizes the frames already in VRAM, no download/upload
        scaler = "scale_cuda" if gpu_frames else "scale"
        cmd += ["-vf", f"{scaler}=-2:{target_height}"]

    quality = str(quality)
    if codec == "h264_nvenc":
        # No -qmin/-qmax: pinning them to the -cq value turns VBR into constant-QP,
        # which ignores -maxrate and can make the output far bigger than the source.
        cmd += ["-c:v", "h264_nvenc", "-rc", "vbr",
                "-cq:v", quality,
                "-b:v", "0", "-maxrate", "4M", "-bufsize", "6M", "-preset", "slow"]
    elif codec == "hevc_nvenc":
        # Higher maxrate for 4K sources so peaks are not starved
        maxrate = "20M" if (target_height == 0 or target_height > 1200) else "8M"
        # No -qmin/-qmax: pinning them to the -cq value turns VBR into constant-QP,
        # which ignores -maxrate and can make the output far bigger than the source.
        cmd += ["-c:v", "hevc_nvenc", "-profile:v", "main", "-rc", "vbr",
                "-cq:v", quality,
                "-b:v", "0", "-maxrate", maxrate, "-bufsize", maxrate,
                "-preset", "slow", "-spatial_aq", "1", "-tag:v", "hvc1"]
    else:
        raise AttributeError(f"Unknown codec: {codec}")

    if audio_filter:
        # Audio is filtered in the same pass as the video encode, so the file
        # is never rewritten a second time just to touch the sound
        cmd += ["-af", audio_filter, "-c:a", "aac", "-b:a", audio_bitrate]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += ["-map_metadata", "0",  # keep creation_time and other original tags
            "-metadata", f"{ENCODER_TAG}={ENCODER_VALUE}",
            output_file]
    return cmd


def encode_one_video(video_file, output_file, quality, target_height=0, codec="hevc_nvenc",
                     audio_filter=None, audio_bitrate="128k", gpu_scale=False):
    """Encode a video file with the specified codec and quality.

    Args:
        video_file: Input video path
        output_file: Output video path (full path with extension)
        quality: CQ value for encoding
        target_height: Target height, 0 to keep the original resolution
        codec: Codec to use (h264, hevc, h264_nvenc, hevc_nvenc)
        audio_filter: Optional ffmpeg -af chain applied during this same pass
        audio_bitrate: Audio bitrate used when audio_filter is set
        gpu_scale: Resize on the GPU (scale_cuda) instead of the CPU scaler

    Returns:
        Output filename on success
    """
    if codec == "h264":
        codec = "h264_nvenc"
    if codec == "hevc":
        codec = "hevc_nvenc"

    # Without downscaling, keeping the frames in VRAM produces a bit-identical
    # file while avoiding every frame copy, so it is always worth it. With
    # downscaling it also means using scale_cuda, which needs ~5% more bitrate
    # than the CPU scaler for the same measured quality: opt-in only.
    attempts = (True, False) if (not target_height or gpu_scale) else (False,)
    for gpu_frames in attempts:
        cmd = build_encode_command(video_file, output_file, quality, target_height, codec,
                                   audio_filter=audio_filter, audio_bitrate=audio_bitrate,
                                   gpu_frames=gpu_frames)
        print('\tCommand:', ' '.join(cmd))
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        if result.returncode == 0:
            if result.stdout or result.stderr:
                print(result.stdout, result.stderr)
            return output_file

        if gpu_frames:
            print("\tGPU frame pipeline failed, retrying with CPU frames "
                  f"(this source may not be supported by NVDEC):\n{result.stderr.strip()[:500]}")
        else:
            raise Exception(f"Encoding failed: {result.stderr}")


def normalize_audio_of_video(video_file, destination):
    """Normalize sound level using EBI (legacy function for compatibility)
    Args:
        video_file (_type_): _description_
        destination (_type_): _description_
        quality (_type_): _description_
        bitrate (int, optional): _description_. Defaults to 2.
    """
    ffmpeg_cli = f'ffmpeg-normalize "{video_file}" -o "{destination}" -c:a aac -b:a 128k'
    print(ffmpeg_cli)
    process = subprocess.Popen(ffmpeg_cli,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    shell=True)
    stdout, stderr = process.communicate()
    print(stdout, stderr)
    if process.returncode != 0:
        print(f"Error : {stderr}")
        if "ffmpeg-normalize: not found" in stderr:
            print("You need to install ffmpeg-normalize : pip install ffmpeg-normalize")
        raise Exception(f"Error : {stderr}")


AUDIO_COMPRESSOR = "acompressor=threshold=-20dB:ratio=3:attack=50:release=500"

# Under this integrated loudness the track is essentially silence: a muted or
# covered mic, a silent scene, nothing but the noise floor. Normalizing it
# would only amplify the hiss, and the original is deleted afterwards, so the
# audio is left alone instead.
SILENCE_LOUDNESS = -40.0


def measure_loudness(video_file, target_loudness=-16, true_peak=-1.5, lra=11) -> Optional[dict]:
    """Measure the loudness of the audio track, compressor included.

    The compressor is part of the analysis chain because loudnorm must measure
    the signal it will actually receive, not the untouched original.
    -vn keeps this cheap: decoding the video here would cost as much as the
    encode itself for nothing.

    Returns:
        The loudnorm JSON measurements, or None if they could not be read.
    """
    analyze_filter = (f"{AUDIO_COMPRESSOR},"
                      f"loudnorm=I={target_loudness}:TP={true_peak}:LRA={lra}:print_format=json")
    analyze_cmd = [FFMPEG_BIN, "-hide_banner", "-i", video_file, "-vn",
                   "-af", analyze_filter, "-f", "null", "-"]
    result = subprocess.run(analyze_cmd, capture_output=True, universal_newlines=True)

    # Extract JSON from stderr (ffmpeg outputs analysis there)
    stderr = result.stderr
    json_start = stderr.find('{')
    json_end = stderr.rfind('}') + 1
    if json_start == -1 or json_end <= json_start:
        return None
    try:
        measured = json.loads(stderr[json_start:json_end])
        float(measured['input_i'])  # also rejects a malformed measurement
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    return measured


def build_audio_filter(video_file, target_loudness=-16, true_peak=-1.5, lra=11):
    """Build the audio filter chain: dynamic compression + EBU R128 loudness normalization.

    The chain is meant to be applied during the video encode itself (see
    encode_one_video), so the file is only written once.

    The track is measured first and left untouched when normalizing it would
    do more harm than good: silence that would only be turned into loud hiss.
    A track already at the target level is still processed, since the point of
    this chain is also to even out the dynamics.

    Args:
        video_file (str): Input video file
        target_loudness (int): Target integrated loudness (LUFS) - default -16 for streaming
        true_peak (float): Maximum true peak to avoid clipping - default -1.5
        lra (int): Loudness Range (lower = more consistent volume) - default 11

    Returns:
        str: the ffmpeg -af chain, or None to leave the audio alone
    """
    measured = measure_loudness(video_file, target_loudness=target_loudness,
                                true_peak=true_peak, lra=lra)
    if measured is None:
        # Better to keep the audio as it is than to normalize blindly: the
        # original is deleted once the encode is verified.
        print("\tWarning: could not measure the audio loudness, leaving the audio untouched")
        return None

    measured_i = float(measured['input_i'])
    if measured_i < SILENCE_LOUDNESS:
        print(f"\tAudio is silent or near-silent ({measured_i:.1f} LUFS), leaving it untouched")
        return None

    print(f"\tMeasured audio: I={measured['input_i']}, TP={measured['input_tp']}, "
          f"LRA={measured['input_lra']}, Thresh={measured['input_thresh']}")
    return (f"{AUDIO_COMPRESSOR},"
            f"loudnorm=I={target_loudness}:TP={true_peak}:LRA={lra}:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"linear=true")


def replace_original(video_file, encoded_file, final_output, trash_dir, root_dir):
    """Replace the original with the encoded file, keeping the original's mtime.

    The original is first renamed to a .bak_encode file so that a crash in the
    middle of the operation never loses data, then deleted (or moved to
    trash_dir, mirroring the folder structure).
    """
    original_mtime = os.stat(video_file).st_mtime
    backup = video_file + ".bak_encode"
    os.rename(video_file, backup)
    try:
        shutil.move(encoded_file, final_output)
    except Exception:
        os.rename(backup, video_file)
        raise
    os.utime(final_output, (original_mtime, original_mtime))

    if trash_dir:
        rel_path = os.path.relpath(video_file, root_dir)
        trash_path = os.path.join(trash_dir, rel_path)
        os.makedirs(os.path.dirname(trash_path), exist_ok=True)
        shutil.move(backup, trash_path)
        print(f"\tOriginal moved to trash: {trash_path}")
    else:
        os.remove(backup)


def log_action(log_file, message):
    if not log_file:
        return
    with open(log_file, "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def process_videos(videos_files: List, video_output_size: int, codec: str,
                   normalize_audio=False, video_quality=None, boost_audio=False,
                   target_loudness=-16, audio_bitrate="192k",
                   camera=None, dry_run=False, limit=0, confirm_first=0,
                   trash_dir=None, root_dir=".", min_reduction=10,
                   decode_check=True, log_file=None, gpu_scale=False):
    """Process videos to transcode them, replacing originals only after verification.

    Args:
        videos_files (List): List of videos to process
        video_output_size (int): Target video height, 0 to keep original resolution
        codec (str): Codec to use
        normalize_audio (bool, optional): Normalize audio level using legacy method.
        boost_audio (bool, optional): Use advanced audio compression and EBU R128 normalization.
        target_loudness (int, optional): Target integrated loudness (LUFS).
        audio_bitrate (str, optional): Audio bitrate for normalized audio.
        camera (str, optional): Only process files whose camera model contains this string.
        dry_run (bool, optional): Only list what would be done.
        limit (int, optional): Stop after this many successful encodes (0 = no limit).
        confirm_first (int, optional): Ask confirmation before replacing the first N originals.
        trash_dir (str, optional): Move originals here instead of deleting them.
        root_dir (str): Root directory of the scan (used for trash_dir layout).
        min_reduction (int): Minimum size reduction in % required to replace the original.
        decode_check (bool): Fully decode encoded files to verify them before deleting originals.
        log_file (str, optional): Append a log of every action to this file.
        gpu_scale (bool): Resize on the GPU (scale_cuda) instead of the CPU scaler.
    """
    if not videos_files:
        print("No videos found!")
        return

    stats = {"candidates": 0, "encoded": 0, "kept": 0, "errors": 0,
             "bytes_before": 0, "bytes_after": 0}
    confirm_remaining = confirm_first
    total = len(videos_files)

    for index, video_file in enumerate(videos_files, 1):
        original_name = os.path.basename(video_file)
        original_dir = os.path.dirname(os.path.abspath(video_file))
        base_name = os.path.splitext(original_name)[0]
        base_ext = os.path.splitext(original_name)[1]

        # Camera filter first (cheap, and keeps the output quiet for other files)
        if camera:
            model = get_camera_model(video_file)
            if not model or camera.lower() not in model.lower():
                continue

        print(f'[{index}/{total}] Processing', video_file)

        try:
            probe = ffmpeg.probe(video_file)
        except Exception as e:
            print(f"\tERROR: Unexpected error reading {video_file}:", e, sys.exc_info())
            stats["errors"] += 1
            continue

        if is_already_encoded(probe):
            print("\tSkipping: Already encoded by this script")
            continue

        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
        if not video_streams:
            print("\tSkipping: no video stream")
            continue
        has_audio = any(stream["codec_type"] == "audio" for stream in probe["streams"])
        codec_name = video_streams[0].get('codec_name')
        height = video_streams[0].get('height')
        if not height:
            print("\tSkipping: could not read video height")
            continue
        height = int(height)

        if codec_name == 'hevc':
            print("\tAlready in HEVC, don't touch it.")
            continue

        # Use smaller of target size or actual video height (0 = keep original)
        if video_output_size and video_output_size < height:
            effective_output_size = video_output_size
            print(f"\tDownscaling from {height} to {effective_output_size}")
        else:
            effective_output_size = height

        if 'tags' in video_streams[0]:
            creation_time = video_streams[0]['tags'].get('creation_time')
        else:
            creation_time = None

        # Auto-select quality based on resolution if not specified
        # Recommended CRF settings for x264/x265:
        #   RF 18-22 for 480p/576p SD
        #   RF 19-23 for 720p HD
        #   RF 20-24 for 1080p FHD
        #   RF 22-28 for 2160p 4K UHD
        auto_quality = video_quality
        if auto_quality is None:
            if effective_output_size > 2200:
                auto_quality = 25  # 8K
            elif effective_output_size > 1200:
                auto_quality = 24  # 2.7K and 4K
            elif effective_output_size > 800:
                auto_quality = 28  # 1080p
            elif effective_output_size > 600:
                auto_quality = 24  # 720p
            else:
                auto_quality = 22  # Low res
        print(f'\t{base_name} {codec_name} {height}p {creation_time} quality={auto_quality}')

        stats["candidates"] += 1
        previous_size = os.stat(video_file).st_size

        if dry_run:
            print(f"\tDRY-RUN: would encode ({human_size(previous_size)})")
            stats["bytes_before"] += previous_size
            continue

        if limit and stats["encoded"] >= limit:
            print(f"\tLimit of {limit} encodes reached, stopping.")
            break

        # Determine output extension based on codec.
        # HEVC goes into .mp4 with the hvc1 tag: better compatibility with
        # NAS indexing, TVs and Apple devices than .mkv.
        output_ext = ".mp4"

        # Create temp file for encoding (hidden name so a crashed run's
        # leftovers are ignored by the next scan)
        temp_fd, temp_output = tempfile.mkstemp(suffix=output_ext, prefix=TEMP_PREFIX, dir=original_dir)
        os.close(temp_fd)

        try:
            # Handle different audio processing options
            scale_to = effective_output_size if effective_output_size < height else 0
            if (boost_audio or normalize_audio) and not has_audio:
                print("\tNo audio stream, skipping audio normalization")

            if boost_audio and has_audio:
                # The filter runs during the video encode itself: the file is
                # written once instead of being fully rewritten for the audio
                # and then read back for the video.
                print(f"\tBoost and normalize audio with compression and EBU R128 (target: {target_loudness} LUFS)")
                audio_filter = build_audio_filter(video_file, target_loudness=target_loudness)
                encode_one_video(video_file, temp_output, auto_quality, scale_to, codec=codec,
                                 audio_filter=audio_filter, audio_bitrate=audio_bitrate,
                                 gpu_scale=gpu_scale)
            elif normalize_audio and has_audio:
                # Legacy path: ffmpeg-normalize writes its own intermediate file
                temp_audio_fd, temp_audio_file = tempfile.mkstemp(suffix=base_ext, prefix=TEMP_PREFIX, dir=original_dir)
                os.close(temp_audio_fd)
                try:
                    print("\tNormalize sound level with ffmpeg-normalize (legacy method)")
                    normalize_audio_of_video(video_file, temp_audio_file)
                    encode_one_video(temp_audio_file, temp_output, auto_quality, scale_to,
                                     codec=codec, gpu_scale=gpu_scale)
                finally:
                    if os.path.exists(temp_audio_file):
                        os.remove(temp_audio_file)
            else:
                encode_one_video(video_file, temp_output, auto_quality, scale_to, codec=codec,
                                 gpu_scale=gpu_scale)

            # Verify the encoded file BEFORE touching the original
            ok, verify_message = verify_encoded_file(probe, temp_output, decode_check=decode_check)
            if not ok:
                print(f"\tERROR: Verification failed, keeping original: {verify_message}")
                log_action(log_file, f"VERIFY-FAILED {video_file} : {verify_message}")
                os.remove(temp_output)
                stats["errors"] += 1
                continue
            print(f"\tVerification: {verify_message}")

            # Check if we reduced size enough
            new_size = os.stat(temp_output).st_size
            reduction = new_size / previous_size

            if reduction > 1 - min_reduction / 100:
                print(f"\tWARNING: Size reduction not significant ({(1-reduction)*100:.1f}%), keeping original")
                log_action(log_file, f"KEPT {video_file} : reduction only {(1-reduction)*100:.1f}%")
                os.remove(temp_output)
                stats["kept"] += 1
                continue

            print(f'\tReduced file size by {(1-reduction)*100:.1f}% ({human_size(previous_size)} -> {human_size(new_size)})')
            final_output = os.path.join(original_dir, base_name + output_ext)

            if confirm_remaining > 0:
                # Move the temp file to a visible name so the user can play it
                preview_file = os.path.join(original_dir, base_name + "_reencoded" + output_ext)
                shutil.move(temp_output, preview_file)
                temp_output = preview_file
                print(f"\t>>> Please check the quality of:\n\t>>>   {preview_file}\n\t>>> against the original:\n\t>>>   {video_file}")
                if click.confirm("\tReplace the original (it will be removed)?", default=True):
                    confirm_remaining -= 1
                    replace_original(video_file, preview_file, final_output, trash_dir, root_dir)
                else:
                    os.remove(preview_file)
                    print("\tOriginal kept, encoded file removed.")
                    if not click.confirm("\tContinue with the next videos?", default=False):
                        print("\tAborted by user.")
                        break
                    continue
            else:
                replace_original(video_file, temp_output, final_output, trash_dir, root_dir)

            print(f"\tReplaced original with: {final_output}")
            log_action(log_file, f"ENCODED {video_file} -> {final_output} : {human_size(previous_size)} -> {human_size(new_size)} ({(1-reduction)*100:.1f}% saved)")
            stats["encoded"] += 1
            stats["bytes_before"] += previous_size
            stats["bytes_after"] += new_size

        except KeyboardInterrupt:
            print("\n\tInterrupted by user, cleaning up temp file.")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            break
        except Exception as e:
            print(f"\tERROR during encoding: {e}")
            log_action(log_file, f"ERROR {video_file} : {e}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            stats["errors"] += 1
            continue

    # Summary
    print("\n=== Summary ===")
    if dry_run:
        print(f"Candidates to encode: {stats['candidates']} ({human_size(stats['bytes_before'])})")
    else:
        saved = stats["bytes_before"] - stats["bytes_after"]
        print(f"Encoded: {stats['encoded']}  (saved {human_size(saved)})")
        print(f"Kept (not enough reduction): {stats['kept']}")
        print(f"Errors: {stats['errors']}")
    log_action(log_file, f"SUMMARY encoded={stats['encoded']} kept={stats['kept']} errors={stats['errors']} saved={human_size(stats['bytes_before'] - stats['bytes_after'])}")


@click.command()
@click.argument('directory', default='.', type=click.Path(exists=True, file_okay=False))
@click.option('-s', '--video_output_size', default=0, type=int, help='Max video height (0 = keep original resolution (default), e.g. 1080, 720)')
@click.option('-q', '--video_quality', default=None, type=int, help='Video quality from 0 (high) to 51 (low). Auto-selected if not specified.')
@click.option('-c', '--codec', default='hevc', help='Codec to use (hevc (default), h264)')
@click.option('--camera', default=None, help='Only process videos whose camera model contains this string (needs exiftool), e.g. "DMC-G8" for a Lumix G80/G81/G85')
@click.option('--dry-run', is_flag=True, default=False, help='Only list the videos that would be encoded, without touching anything')
@click.option('--limit', default=0, type=int, help='Stop after N successful encodes (0 = no limit)')
@click.option('--confirm-first', default=3, type=int, help='Ask for manual confirmation before replacing the first N originals (0 = fully automatic). Default: 3')
@click.option('--trash-dir', default=None, type=click.Path(file_okay=False), help='Move originals to this directory instead of deleting them')
@click.option('--min-reduction', default=10, type=int, help='Minimum size reduction in % required to replace the original (default: 10)')
@click.option('--no-decode-check', is_flag=True, default=False, help='Skip the full decode verification of encoded files (faster but less safe)')
@click.option('--no-recursive', is_flag=True, default=False, help='Do not scan subdirectories')
@click.option('--gpu-scale', is_flag=True, default=False, help='Resize on the GPU (scale_cuda): frees the CPU but needs ~5% more bitrate for the same quality')
@click.option('--log-file', default='encode_video.log', type=click.Path(dir_okay=False), help='Log every action to this file (default: encode_video.log)')
@click.option('-n', '--normalize_audio', is_flag=True, help='Normalize audio level (legacy method)', default=False)
@click.option('-b/-B', '--boost_audio/--no_boost_audio', default=True, help='Boost and normalize audio with compression and EBU R128 (default: on, skipped on silent or already-levelled tracks)')
@click.option('--two_pass_audio', is_flag=True, default=False, help='Kept for compatibility: the loudness is always measured first, so normalization is already two-pass')
@click.option('--target_loudness', default=-16, type=int, help='Target integrated loudness in LUFS (default: -16 for streaming)')
@click.option('--audio_bitrate', default='192k', help='Audio bitrate for normalized audio (default: 192k)')
def encode(directory, video_output_size, video_quality, codec, camera, dry_run, limit,
           confirm_first, trash_dir, min_reduction, no_decode_check, no_recursive, log_file,
           gpu_scale, normalize_audio, boost_audio, two_pass_audio, target_loudness, audio_bitrate):
    """Encode all videos in DIRECTORY (recursively), replacing originals only
    after the encoded file has been verified.

    Videos already encoded by this script (metadata tag) or already in HEVC
    are automatically skipped.

    Recommended workflow on a large archive:

    \b
    1. Inventory:      encode_video.py --dry-run --camera DMC-G8 /media/NAS-Photos
    2. First real run: encode_video.py --camera DMC-G8 --limit 5 --confirm-first 5 /media/NAS-Photos
    3. Full run:       encode_video.py --camera DMC-G8 --confirm-first 0 /media/NAS-Photos

    Audio processing options:

    \b
    - Audio compression + EBU R128 normalization is on by default (-b). The
      track is measured first and left untouched when it is silent or already
      at the target level.
    - Use -B / --no_boost_audio to keep the audio exactly as it is
    - Use -n for legacy ffmpeg-normalize audio normalization instead
    - Adjust --target_loudness for different platforms (-16 for streaming, -23 for broadcast)
    """
    # Validate audio options
    if two_pass_audio:
        click.echo("Note: --two_pass_audio is now the default, the loudness is always measured first.")

    if normalize_audio and boost_audio:
        boost_explicit = (click.get_current_context().get_parameter_source('boost_audio')
                          is not click.core.ParameterSource.DEFAULT)
        if boost_explicit:
            click.echo("Warning: Both -n and -b specified. Using advanced boost audio (-b) method.")
            normalize_audio = False
        else:
            # -n on its own asks for the legacy method, not for both
            boost_audio = False

    if camera and shutil.which("exiftool") is None:
        click.echo("ERROR: --camera requires exiftool. Install it with: sudo apt install libimage-exiftool-perl")
        sys.exit(1)

    if not dry_run:
        nvenc_codec = {"h264": "h264_nvenc", "hevc": "hevc_nvenc"}.get(codec, codec)
        ok, message = check_nvenc_works(nvenc_codec)
        if not ok:
            click.echo(f"ERROR: GPU encoder {nvenc_codec} is not working:\n{message}")
            if "version mismatch" in message.lower() or "cuInit" in message:
                click.echo("Hint: the NVIDIA driver was probably updated without a reboot. Reboot and try again.")
            sys.exit(1)

    if trash_dir:
        os.makedirs(trash_dir, exist_ok=True)

    click.echo(f"Scanning {directory}" + ("" if no_recursive else " (recursively)") + "...")
    video_list = find_videos(directory, recursive=not no_recursive)
    if trash_dir:
        # Never rescan originals that were moved to the trash directory
        trash_abs = os.path.abspath(trash_dir)
        video_list = [v for v in video_list
                      if not os.path.abspath(v).startswith(trash_abs + os.sep)]
    click.echo(f"Found {len(video_list)} video files" + (f", filtering on camera model containing '{camera}'" if camera else ""))

    process_videos(video_list, video_output_size, codec,
                   normalize_audio=normalize_audio, video_quality=video_quality,
                   boost_audio=boost_audio,
                   target_loudness=target_loudness, audio_bitrate=audio_bitrate,
                   camera=camera, dry_run=dry_run, limit=limit,
                   confirm_first=0 if dry_run else confirm_first,
                   trash_dir=trash_dir, root_dir=directory,
                   min_reduction=min_reduction, decode_check=not no_decode_check,
                   log_file=None if dry_run else log_file, gpu_scale=gpu_scale)
    click.echo("Done")


if __name__ == "__main__":
   encode()
