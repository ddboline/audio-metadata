__all__ = [
	'LAMEEncodingFlags',
	'LAMEHeader',
	'LAMEReplayGain',
	'MP3',
	'MP3StreamInfo',
	'MPEGFrameHeader',
	'VBRIHeader',
	'VBRIToC',
	'XingHeader',
	'XingToC'
]

import os
import re
import struct

import bitstruct
import more_itertools
from attr import attrib, attrs

from .id3v1 import ID3v1
from .id3v2 import ID3v2, ID3v2Frames
from .models import Format, StreamInfo
from .tables import (
	LAMEBitrateMode,
	LAMEChannelMode,
	LAMEPreset,
	LAMEReplayGainOrigin,
	LAMEReplayGainType,
	LAMESurroundInfo,
	MP3BitrateMode,
	MP3Bitrates,
	MP3ChannelMode,
	MP3SampleRates,
	MP3SamplesPerFrame
)
from ..exceptions import InvalidFormat, InvalidFrame, InvalidHeader
from ..structures import DictMixin, ListMixin
from ..utils import (
	datareader,
	humanize_bitrate,
	humanize_filesize,
	humanize_sample_rate
)


@attrs(repr=False)
class LAMEReplayGain(DictMixin):
	peak = attrib()
	track_type = attrib(converter=LAMEReplayGainType)
	track_origin = attrib(converter=LAMEReplayGainOrigin)
	track_adjustment = attrib()
	album_type = attrib(converter=LAMEReplayGainType)
	album_origin = attrib(converter=LAMEReplayGainOrigin)
	album_adjustment = attrib()

	@datareader
	@classmethod
	def load(cls, data):
		peak_data = struct.unpack('>I', data.read(4))[0]

		if peak_data == 0:
			gain_peak = None
		else:
			gain_peak = peak_data / 2 ** 23

		track_gain_type_, track_gain_origin_, track_gain_sign, track_gain_adjustment_ = bitstruct.unpack(
			'u3 u3 b1 u9',
			data.read(2)
		)

		track_gain_type = LAMEReplayGainType(track_gain_type_)
		track_gain_origin = LAMEReplayGainOrigin(track_gain_origin_)
		track_gain_adjustment = track_gain_adjustment_ / 10.0

		if track_gain_sign:
			track_gain_adjustment *= -1

		album_gain_type_, album_gain_origin_, album_gain_sign, album_gain_adjustment_ = bitstruct.unpack(
			'u3 u3 b1 u9',
			data.read(2)
		)

		album_gain_type = LAMEReplayGainType(album_gain_type_)
		album_gain_origin = LAMEReplayGainOrigin(album_gain_origin_)
		album_gain_adjustment = album_gain_adjustment_ / 10.0

		if album_gain_sign:
			album_gain_adjustment *= -1

		return cls(
			gain_peak,
			track_gain_type,
			track_gain_origin,
			track_gain_adjustment,
			album_gain_type,
			album_gain_origin,
			album_gain_adjustment
		)


@attrs(repr=False)
class LAMEEncodingFlags(DictMixin):
	nogap_continuation = attrib(converter=bool)
	nogap_continued = attrib(converter=bool)
	nssafejoint = attrib(converter=bool)
	nspsytune = attrib(converter=bool)


@attrs(repr=False)
class LAMEHeader(DictMixin):
	_crc = attrib()
	version = attrib()
	revision = attrib()
	ath_type = attrib()
	audio_crc = attrib()
	audio_size = attrib()
	bitrate = attrib()
	bitrate_mode = attrib(converter=LAMEBitrateMode)
	channel_mode = attrib(converter=LAMEChannelMode)
	delay = attrib()
	encoding_flags = attrib(converter=LAMEEncodingFlags.from_mapping)
	lowpass_filter = attrib()
	mp3_gain = attrib()
	noise_shaping = attrib()
	padding = attrib()
	preset = attrib(converter=LAMEPreset)
	replay_gain = attrib()
	source_sample_rate = attrib()
	surround_info = attrib(converter=LAMESurroundInfo)
	unwise_settings_used = attrib()

	def __repr__(self):
		repr_dict = {}

		for k, v in sorted(self.items()):
			if k == 'bitrate':
				repr_dict[k] = humanize_bitrate(v)
			elif k == 'audio_size':
				repr_dict[k] = humanize_filesize(v, precision=2)
			elif not k.startswith('_'):
				repr_dict[k] = v

		return super().__repr__(repr_dict=repr_dict)

	@datareader
	@classmethod
	def load(cls, data, xing_quality):
		encoder = data.read(9)
		if not encoder.startswith(b'LAME'):
			raise InvalidHeader('Valid LAME header not found.')

		version_match = re.search(rb'LAME(\d+)\.(\d+)', encoder)
		if version_match:
			version = tuple(int(part) for part in version_match.groups())
		else:
			version = None

		revision, bitrate_mode_ = bitstruct.unpack(
			'u4 u4',
			data.read(1)
		)
		bitrate_mode = LAMEBitrateMode(bitrate_mode_)

		# TODO: Decide what, if anything, to do with the different meanings in LAME.
		# quality = (100 - xing_quality) % 10
		# vbr_quality = (100 - xing_quality) // 10

		lowpass_filter = struct.unpack(
			'B',
			data.read(1)
		)[0] * 100

		replay_gain = LAMEReplayGain.load(data)

		flags_ath = bitstruct.unpack_dict(
			'b1 b1 b1 b1 u4',
			[
				'nogap_continuation',
				'nogap_continued',
				'nssafejoint',
				'nspsytune',
				'ath_type'
			],
			data.read(1)
		)

		ath_type = flags_ath.pop('ath_type')
		encoding_flags = LAMEEncodingFlags(
			flags_ath['nogap_continuation'],
			flags_ath['nogap_continued'],
			flags_ath['nssafejoint'],
			flags_ath['nspsytune']
		)

		# TODO: Different representation for VBR minimum bitrate vs CBR/ABR specified bitrate?
		# Can only go up to 255.
		bitrate = struct.unpack(
			'B',
			data.read(1)
		)[0] * 1000

		delay, padding = bitstruct.unpack(
			'u12 u12',
			data.read(3)
		)

		source_sample_rate, unwise_settings_used, channel_mode_, noise_shaping = bitstruct.unpack(
			'u2 u1 u3 u2',
			data.read(1)
		)
		channel_mode = LAMEChannelMode(channel_mode_)

		mp3_gain = bitstruct.unpack(
			's8',
			data.read(1)
		)[0]

		surround_info_, preset_used_ = bitstruct.unpack(
			'p2 u3 u11',
			data.read(2)
		)
		surround_info = LAMESurroundInfo(surround_info_)

		preset = LAMEPreset(preset_used_)

		audio_size, audio_crc, lame_crc = struct.unpack(
			'>I2s2s',
			data.read(8)
		)

		return cls(
			lame_crc,
			version,
			revision,
			ath_type,
			audio_crc,
			audio_size,
			bitrate,
			bitrate_mode,
			channel_mode,
			delay,
			encoding_flags,
			lowpass_filter,
			mp3_gain,
			noise_shaping,
			padding,
			preset,
			replay_gain,
			source_sample_rate,
			surround_info,
			unwise_settings_used
		)


class XingToC(ListMixin):
	item_label = 'entries'


@attrs(repr=False)
class XingHeader(DictMixin):
	_lame = attrib()
	num_frames = attrib()
	num_bytes = attrib()
	toc = attrib(converter=XingToC)
	quality = attrib()

	@datareader
	@classmethod
	def load(cls, data):
		if data.read(4) not in [b'Xing', b'Info']:
			raise InvalidHeader('Valid Xing header not found.')

		flags = struct.unpack('>i', data.read(4))[0]

		num_frames = num_bytes = toc = quality = lame_header = None

		if flags & 1:
			num_frames = struct.unpack('>I', data.read(4))[0]

		if flags & 2:
			num_bytes = struct.unpack('>I', data.read(4))[0]

		if flags & 4:
			toc = XingToC(bytearray(data.read(100)))

		if flags & 8:
			quality = struct.unpack('>I', data.read(4))[0]

		if data.peek(4) == b'LAME':
			lame_header = LAMEHeader.load(data, quality)

		return cls(lame_header, num_frames, num_bytes, toc, quality)


class VBRIToC(ListMixin):
	item_label = 'entries'


@attrs(repr=False)
class VBRIHeader(DictMixin):
	version = attrib()
	delay = attrib()
	quality = attrib()
	num_bytes = attrib()
	num_frames = attrib()
	num_toc_entries = attrib()
	toc_scale_factor = attrib()
	toc_entry_num_bytes = attrib()
	toc_entry_num_frames = attrib()
	toc = attrib(converter=VBRIToC)

	@datareader
	@classmethod
	def load(cls, data):
		if data.read(4) not in [b'VBRI']:
			raise InvalidHeader('Valid VBRI header not found.')

		version = struct.unpack('>H', data.read(2))[0]
		delay = struct.unpack('>e', data.read(2))[0]
		quality = struct.unpack('>H', data.read(2))[0]
		num_bytes = struct.unpack('>I', data.read(4))[0]
		num_frames = struct.unpack('>I', data.read(4))[0]
		num_toc_entries = struct.unpack('>H', data.read(2))[0]
		toc_scale_factor = struct.unpack('>H', data.read(2))[0]
		toc_entry_num_bytes = struct.unpack('>H', data.read(2))[0]
		toc_entry_num_frames = struct.unpack('>H', data.read(2))[0]

		toc_size = num_toc_entries * toc_entry_num_bytes

		if toc_entry_num_bytes not in [2, 4]:
			raise InvalidHeader('Invalid VBRI TOC entry size.')

		if toc_entry_num_bytes == 2:
			pattern = '>H'
		else:
			pattern = '>I'

		toc = VBRIToC(
			struct.unpack(pattern, data.read(toc_entry_num_bytes))[0]
			for _ in range(toc_size // toc_entry_num_bytes)
		)

		return cls(
			version,
			delay,
			quality,
			num_bytes,
			num_frames,
			num_toc_entries,
			toc_scale_factor,
			toc_entry_num_bytes,
			toc_entry_num_frames,
			toc
		)


@attrs(repr=False)
class MPEGFrameHeader(DictMixin):
	_start = attrib()
	_size = attrib()
	_vbri = attrib()
	_xing = attrib()
	version = attrib()
	layer = attrib()
	protected = attrib()
	padded = attrib()
	bitrate = attrib()
	channel_mode = attrib(converter=MP3ChannelMode)
	channels = attrib()
	sample_rate = attrib()

	def __repr__(self):
		repr_dict = {}

		for k, v in sorted(self.items()):
			if k == 'bitrate':
				repr_dict[k] = humanize_bitrate(v)
			elif k == 'sample_rate':
				repr_dict[k] = humanize_sample_rate(v)
			elif not k.startswith('_'):
				repr_dict[k] = v

		return super().__repr__(repr_dict=repr_dict)

	@datareader
	@classmethod
	def load(cls, data):
		frame_start = data.tell()

		sync, version_id, layer_index, protection = bitstruct.unpack(
			'u11 u2 u2 b1',
			data.read(2)
		)

		if sync != 2047:
			raise InvalidFrame('Not a valid MPEG audio frame.')

		version = [2.5, None, 2, 1][version_id]

		layer = 4 - layer_index

		protected = not protection

		bitrate_index, sample_rate_index, padded = bitstruct.unpack(
			'u4 u2 u1',
			data.read(1)
		)

		if (
			version_id == 1
			or layer_index == 0
			or bitrate_index == 0
			or bitrate_index == 15
			or sample_rate_index == 3
		):
			raise InvalidFrame('Not a valid MPEG audio frame.')

		channel_mode = MP3ChannelMode(bitstruct.unpack('u2', data.read(1))[0])
		channels = 1 if channel_mode == 3 else 2

		bitrate = MP3Bitrates[(version, layer)][bitrate_index] * 1000
		sample_rate = MP3SampleRates[version][sample_rate_index]

		samples_per_frame, slot_size = MP3SamplesPerFrame[(version, layer)]

		frame_size = (((samples_per_frame // 8 * bitrate) // sample_rate) + padded) * slot_size

		vbri_header = None
		xing_header = None
		if layer == 3:
			if version == 1:
				if channel_mode != 3:
					xing_header_start = 36
				else:
					xing_header_start = 21
			elif channel_mode != 3:
				xing_header_start = 21
			else:
				xing_header_start = 13

			data.seek(frame_start + xing_header_start, os.SEEK_SET)

			if data.peek(4) in [b'Xing', b'Info']:
				xing_header = XingHeader.load(data.read(frame_size))

			data.seek(frame_start + 36, os.SEEK_SET)

			if data.peek(4) == b'VBRI':
				vbri_header = VBRIHeader.load(data)

		return cls(
			frame_start,
			frame_size,
			vbri_header,
			xing_header,
			version,
			layer,
			protected,
			padded,
			bitrate,
			channel_mode,
			channels,
			sample_rate
		)


@attrs(repr=False)
class MP3StreamInfo(StreamInfo):
	_start = attrib()
	_end = attrib()
	_size = attrib()
	_vbri = attrib()
	_xing = attrib()
	version = attrib()
	layer = attrib()
	protected = attrib()
	bitrate = attrib()
	bitrate_mode = attrib(converter=MP3BitrateMode)
	channel_mode = attrib(converter=MP3ChannelMode)
	channels = attrib()
	duration = attrib()
	sample_rate = attrib()

	@staticmethod
	def find_mp3_frames(data):
		frames = []
		cached_frames = None
		buffer_size = 128
		buffer = data.peek(buffer_size)

		while len(buffer) >= buffer_size:
			sync_start = buffer.find(b'\xFF')

			if sync_start == -1:
				data.seek(buffer_size, os.SEEK_CUR)
				buffer = data.peek(buffer_size)
				continue
			else:
				data.seek(sync_start, os.SEEK_CUR)

			if bitstruct.unpack('u11', data.peek(2))[0] == 2047:
				for _ in range(4):
					try:
						frame = MPEGFrameHeader.load(data)
						frames.append(frame)
						if frame._xing:
							break
						data.seek(frame._start + frame._size, os.SEEK_SET)
					except (InvalidFrame, bitstruct.Error):
						data.seek(1, os.SEEK_CUR)
						break
			else:
				data.seek(sync_start + 1, os.SEEK_CUR)

			if frames and (len(frames) >= 4 or frames[0]._xing):
				break

			if len(frames) >= 2 and cached_frames is None:
				cached_frames = frames.copy()

			del frames[:]

			buffer = data.peek(buffer_size)

		if not frames:
			if not cached_frames:
				raise InvalidFormat("Missing XING header and insufficient MPEG frames.")
			else:
				frames = cached_frames

		return frames

	@datareader
	@classmethod
	def load(cls, data):
		frames = cls.find_mp3_frames(data)

		samples_per_frame, _ = MP3SamplesPerFrame[(frames[0].version, frames[0].layer)]

		data.seek(0, os.SEEK_END)
		end_pos = data.tell()

		# This is an arbitrary amount that should hopefully encompass all end tags.
		# Starting low so as not to add unnecessary processing time.
		chunk_size = 64 * 1024
		if end_pos > chunk_size:
			data.seek(-chunk_size, os.SEEK_END)
		else:
			data.seek(0, os.SEEK_SET)

		end_buffer = data.read()

		end_tag_offset = 0
		for tag_type in [b'APETAGEX', b'LYRICSBEGIN', b'TAG']:
			tag_offset = end_buffer.rfind(tag_type)

			if tag_offset > 0:
				tag_offset = len(end_buffer) - tag_offset

				if tag_offset > end_tag_offset:
					end_tag_offset = tag_offset

		audio_start = frames[0]._start
		audio_end = end_pos - end_tag_offset
		audio_size = audio_end - audio_start

		bitrate_mode = MP3BitrateMode.UNKNOWN

		vbri_header = frames[0]._vbri
		xing_header = frames[0]._xing
		if xing_header:
			num_samples = samples_per_frame * xing_header.num_frames

			# I prefer to include the Xing/LAME header as part of the audio.
			# Google Music seems to do so for calculating client ID.
			# Haven't tested in too many other scenarios.
			# But, there should be enough low-level info for people to calculate this if desired.
			if xing_header._lame:
				# Old versions of LAME wrote invalid delay/padding for
				# short MP3s with low bitrate.
				# Subtract them only them if there would be samples left.
				lame_padding = xing_header._lame.delay + xing_header._lame.padding
				if lame_padding < num_samples:
					num_samples -= lame_padding

				if xing_header._lame.bitrate_mode in [1, 8]:
					bitrate_mode = MP3BitrateMode.CBR
				elif xing_header._lame.bitrate_mode in [2, 9]:
					bitrate_mode = MP3BitrateMode.ABR
				elif xing_header._lame.bitrate_mode in [3, 4, 5, 6]:
					bitrate_mode = MP3BitrateMode.VBR
		elif vbri_header:
			num_samples = samples_per_frame * vbri_header.num_frames
			bitrate_mode = MP3BitrateMode.VBR
		else:
			if more_itertools.all_equal([frame['bitrate'] for frame in frames]):
				bitrate_mode = MP3BitrateMode.CBR

			num_samples = samples_per_frame * (audio_size / frames[0]._size)

		if bitrate_mode is MP3BitrateMode.CBR:
			bitrate = frames[0].bitrate
		else:
			# Subtract Xing/LAME frame size from audio_size for bitrate calculation accuracy.
			if xing_header:
				bitrate = ((audio_size - frames[0]._size) * 8 * frames[0].sample_rate) / num_samples
			else:
				bitrate = (audio_size * 8 * frames[0].sample_rate) / num_samples

		duration = (audio_size * 8) / bitrate

		version = frames[0].version
		layer = frames[0].layer
		protected = frames[0].protected
		sample_rate = frames[0].sample_rate
		channel_mode = frames[0].channel_mode
		channels = frames[0].channels

		return cls(
			audio_start,
			audio_end,
			audio_size,
			vbri_header,
			xing_header,
			version,
			layer,
			protected,
			bitrate,
			bitrate_mode,
			channel_mode,
			channels,
			duration,
			sample_rate
		)


class MP3(Format):
	"""MP3 file format object.

	Extends :class:`Format`.

	Attributes:
		pictures (list): A list of :class:`ID3v2Picture` objects.
		streaminfo (MP3StreamInfo): The audio stream information.
		tags (ID3v2Frames): The ID3v2 tag frames, if present.
	"""

	tags_type = ID3v2Frames

	@classmethod
	def load(cls, data):
		self = super()._load(data)

		try:
			self._id3 = ID3v2.load(self._obj)
			self.pictures = self._id3.pictures
			self.tags = self._id3.tags
		except (InvalidFrame, InvalidHeader):
			self._obj.seek(0, os.SEEK_SET)

		self.streaminfo = MP3StreamInfo.load(self._obj)

		# Use ID3v1 if present and ID3v2 is not.
		if '_id3' not in self:
			self._obj.seek(self.streaminfo._start + self.streaminfo._size, os.SEEK_SET)

			end_buffer = self._obj.read()

			apev2_index = end_buffer.find(b'APETAGEX')
			if apev2_index != -1:
				end_buffer = end_buffer[apev2_index + 8:]

			id3v1_index = end_buffer.find(b'TAG')
			if id3v1_index != -1:
				id3v1 = ID3v1.load(end_buffer[id3v1_index : id3v1_index + 128])
				self._id3 = id3v1
				self.tags = self._id3.tags

		self._obj.close()

		return self
