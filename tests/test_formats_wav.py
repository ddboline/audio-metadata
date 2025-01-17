import pytest
from audio_metadata import (
	WAV,
	InvalidChunk,
	InvalidHeader,
	RIFFTags
)


def test_RIFFTags_invalid():
	with pytest.raises(InvalidChunk):
		RIFFTags.load(b'NOTINFO')


def test_WAV_invalid_header():
	with pytest.raises(InvalidHeader, match="Valid WAVE header not found"):
		WAV.load(b'TEST0000WAVE')

	with pytest.raises(InvalidHeader):
		WAV.load(b'RIFF0000TEST')


def test_WAV_ID3_invalid_header():
	with pytest.raises(InvalidHeader):
		WAV.load(b'RIFF0000WAVEid3 1234')


def test_WAV_invalid_stream_info():
	with pytest.raises(InvalidHeader, match="Valid WAVE stream info not found"):
		WAV.load(b'RIFF0000WAVE')
