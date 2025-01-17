from pathlib import Path

import bitstruct
import pytest
from audio_metadata import (
	FLAC,
	FLACApplication,
	FLACCueSheet,
	FLACCueSheetIndex,
	FLACCueSheetTrack,
	FLACMetadataBlock,
	FLACPadding,
	FLACSeekPoint,
	FLACSeekTable,
	InvalidHeader
)


def test_FLAC_invalid_header():
	with pytest.raises(InvalidHeader, match="Valid FLAC header not found"):
		FLAC.load(b'TEST')


def test_FLAC_invalid_block_type():
	with pytest.raises(InvalidHeader, match="FLAC header contains invalid block type"):
		FLAC.load(b'fLaC\xff\x00\x00\x00')


def test_FLAC_reserved_block_type():
	orig = (Path(__file__).parent / 'files' / 'audio' / 'test-flac-vorbis.flac').read_bytes()
	flac_data = orig[0:4] + bitstruct.pack('b1 u7 u24', False, 10, 0) + orig[4:]
	flac = FLAC.load(flac_data)

	assert flac._blocks[0] == FLACMetadataBlock(10, b'')


def test_FLACApplication():
	application_init = FLACApplication(
		id='aiff',
		data=b'FORM\x02\xe0\x9b\x08AIFF'
	)
	application_load = FLACApplication.load(
		b'aiffFORM\x02\xe0\x9b\x08AIFF'
	)

	assert application_init == application_load
	assert application_init.id == application_load.id == 'aiff'
	assert application_init.data == application_load.data == b'FORM\x02\xe0\x9b\x08AIFF'
	assert repr(application_init) == repr(application_load) == '<FLACApplication (aiff)>'


def test_FLACCueSheetIndex():
	cuesheet_index_init = FLACCueSheetIndex(1, 0)
	cuesheet_index_load = FLACCueSheetIndex.load(
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00'
	)

	assert cuesheet_index_init == cuesheet_index_load
	assert cuesheet_index_init.number == cuesheet_index_load.number == 1
	assert cuesheet_index_init.offset == cuesheet_index_load.offset == 0
	assert repr(cuesheet_index_init) == repr(cuesheet_index_load) == "<FLACCueSheetIndex ({'number': 1, 'offset': 0})>"

	cuesheet_index_init = FLACCueSheetIndex(2, 588)
	cuesheet_index_load = FLACCueSheetIndex.load(
		b'\x00\x00\x00\x00\x00\x00\x02L\x02\x00\x00\x00'
	)

	assert cuesheet_index_init == cuesheet_index_load
	assert cuesheet_index_init.number == cuesheet_index_load.number == 2
	assert cuesheet_index_init.offset == cuesheet_index_load.offset == 588
	assert repr(cuesheet_index_init) == repr(cuesheet_index_load) == "<FLACCueSheetIndex ({'number': 2, 'offset': 588})>"


def test_FLACCueSheetTrack():
	cuesheet_track_init = FLACCueSheetTrack(
		1,
		0,
		'123456789012',
		0,
		False,
		[FLACCueSheetIndex(1, 0)]
	)
	cuesheet_track_load = FLACCueSheetTrack.load(
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x01123456789012'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00'
	)

	assert cuesheet_track_init == cuesheet_track_load
	assert cuesheet_track_init.track_number == cuesheet_track_load.track_number == 1
	assert cuesheet_track_init.offset == cuesheet_track_load.offset == 0
	assert cuesheet_track_init.isrc == cuesheet_track_load.isrc == '123456789012'
	assert cuesheet_track_init.type == cuesheet_track_load.type == 0
	assert cuesheet_track_init.pre_emphasis is False
	assert cuesheet_track_load.pre_emphasis is False

	cuesheet_track_init = FLACCueSheetTrack(
		2,
		44100,
		'',
		1,
		True,
		[
			FLACCueSheetIndex(1, 0),
			FLACCueSheetIndex(2, 588),
		],
	)
	cuesheet_track_load = FLACCueSheetTrack.load(
		b'\x00\x00\x00\x00\x00\x00\xacD\x02\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc0\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02L\x02\x00\x00\x00'
	)

	assert cuesheet_track_init == cuesheet_track_load
	assert cuesheet_track_init.track_number == cuesheet_track_load.track_number == 2
	assert cuesheet_track_init.offset == cuesheet_track_load.offset == 44100
	assert cuesheet_track_init.isrc == cuesheet_track_load.isrc == ''
	assert cuesheet_track_init.type == cuesheet_track_load.type == 1
	assert cuesheet_track_init.pre_emphasis is True
	assert cuesheet_track_load.pre_emphasis is True


def test_FLACCueSheet():
	cuesheet_init = FLACCueSheet(
		[
			FLACCueSheetTrack(
				1,
				0,
				'123456789012',
				0,
				False,
				[FLACCueSheetIndex(1, 0)]
			),
			FLACCueSheetTrack(
				2,
				44100,
				'',
				1,
				True,
				[
					FLACCueSheetIndex(1, 0),
					FLACCueSheetIndex(2, 588),
				],
			),
			FLACCueSheetTrack(
				3,
				88200,
				'',
				0,
				False,
				[FLACCueSheetIndex(1, 0)],
			),
			FLACCueSheetTrack(
				170,
				162496,
				'',
				0,
				False,
				[]
			)
		],
		'1234567890123',
		88200,
		True
	)
	cuesheet_load = FLACCueSheet.load(
		b'1234567890123\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01X\x88\x80\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x01123456789012\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\xacD\x02\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x02L\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01X\x88\x03\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x02z\xc0\xaa\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
	)

	assert cuesheet_init == cuesheet_load
	assert repr(cuesheet_init) == repr(cuesheet_load) == '<FLACCueSheet (4 tracks)>'


def test_FLACMetadataBlock():
	metadata_block = FLACMetadataBlock(
		type=100,
		data=b'\x00' * 10
	)

	assert metadata_block.type == 100
	assert metadata_block.data == b'\x00' * 10
	assert repr(metadata_block) == '<FLACMetadataBlock [100] (10 bytes)>'


def test_FLACPadding():
	padding_init = FLACPadding(10)
	padding_load = FLACPadding.load(b'\x00' * 10)

	assert padding_init == padding_load
	assert repr(padding_init) == repr(padding_load) == '<FLACPadding (10 bytes)>'


def test_FLACSeektable():
	seekpoints = [
		FLACSeekPoint(first_sample, offset, num_samples)
		for first_sample, offset, num_samples in [
			(0, 0, 4096),
			(40960, 140, 4096),
			(86016, 294, 4096),
			(131072, 448, 4096),
			(176128, 602, 4096)
		]
	]

	seektable_init = FLACSeekTable(seekpoints)
	seektable_load = FLACSeekTable.load(
		b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00'
		b'\x00\x00\x00\x00\x00\x00\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x8c\x10\x00'
		b'\x00\x00\x00\x00\x00\x01P\x00\x00\x00\x00\x00\x00\x00\x01&\x10\x00'
		b'\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01\xc0\x10\x00'
		b'\x00\x00\x00\x00\x00\x02\xb0\x00\x00\x00\x00\x00\x00\x00\x02Z\x10\x00'
	)

	assert seektable_init == seektable_load
	assert seektable_init.data == seektable_load.data == seekpoints
