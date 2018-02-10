import json
import re
import subprocess

from glob import glob

MKV_GLOB = '*.mkv'
SRT_GLOB = '*.srt'

EPISODE_INFO_REGEXP = re.compile('[sS]?(?P<season>[0-9]{2})[xXeE](?P<episode>[0-9]{2})')

FFPROBE = 'ffprobe -hide_banner -v quiet -print_format json -show_streams {}'

class MovieInfo(object):
    __slots__ = [
        'episode',
        'mkv_file',
        'season',
        'srt_file',
        'title',
    ]

    def __init__(self, episode=None, mkv_file=None, season=None, srt_file=None, title=None):
        self.episode = episode
        self.mkv_file = mkv_file
        self.season = season
        self.srt_file = srt_file
        self.title = title

        assert mkv_file is not None

def clean_title(title):
    title = title.replace('.', ' ')
    title = title.replace('-', ' ')
    title = title.strip()
    return title

# TODO: This should be a method on MovieInfo
def make_dict_key_for_info(info):
    if info.season is not None:
        return '{} s{}e{}'.format(info.title, info.season, info.episode)
    else:
        return info.title

def make_dict_key_for_match(file_name, match):
    if match is None:
        return file_name
    else:
        title = file_name[:match.start()]
        return '{} s{}e{}'.format(
            clean_title(title),
            match.group('season'),
            match.group('episode'))

def match_to_info(mkv_file, match):
    if match is None:
        return MovieInfo(mkv_file=mkv_file, title=mkv_file)
    else:
        title = mkv_file[:match.start()]
        return MovieInfo(mkv_file=mkv_file,
                         title=clean_title(title),
                         season=match.group('season'),
                         episode=match.group('episode'))

mkvs = glob(MKV_GLOB)
srts = glob(SRT_GLOB)

matches = [(mkv, EPISODE_INFO_REGEXP.search(mkv)) for mkv in mkvs]
infos = dict()

for mkv_file, match in matches:
    info = match_to_info(mkv_file, match)
    infos[make_dict_key_for_info(info)] = info

matches = [(srt, EPISODE_INFO_REGEXP.search(srt)) for srt in srts]

for srt_file, match in matches:
    if match is None:
        print('Failed to extract info for SRT "{}"'.format(srt_file))
    else:
        dict_key = make_dict_key_for_match(srt_file, match)

        if dict_key in infos:
            infos[dict_key].srt_file = srt_file
        else:
            print('No matching info for SRT "{}" (key: "{}")'.format(srt_file, dict_key))

for info in infos.values():
    raw_stream_info = subprocess.check_output(FFPROBE.format(info.mkv_file), shell=True)
    stream_info = json.loads(raw_stream_info.decode('utf-8'))

    video_codec = 'h264'
    audio_codec = 'aac'

    assert len(stream_info['streams']) == 2, "I don't know what to do with so many streams."

    for stream in stream_info['streams']:
        if stream['codec_name'] == video_codec:
            video_codec = 'copy'
        elif stream['codec_name'] == audio_codec:
            audio_codec = 'copy'

    subtitle_file = ''
    subtitle_options = ''

    if info.srt_file is not None:
        subtitle_file = '-i "{}"'.format(info.srt_file)
        subtitle_options = '-c:s mov_text -metadata:s:2 language=eng'

    output_file = info.mkv_file.replace('mkv', 'mp4')

    ffmpeg = 'ffmpeg -i "{mkv}" {sf} -c:v {vc} -c:a {ac} {so} -strict -2 -flags +global_header "{of}"'.format(
        mkv=info.mkv_file,
        sf=subtitle_file,
        vc=video_codec,
        ac=audio_codec,
        so=subtitle_options,
        of=output_file
    )

    print(ffmpeg)
    subprocess.call(ffmpeg, shell=True)
