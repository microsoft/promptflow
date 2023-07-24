import pytest

from promptflow.utils.credential_scrubber import CredentialScrubber


def mock_connection_string():
    connection_str_before_key = 'DefaultEndpointsProtocol=https;AccountName=accountName;'
    connection_str_after_key = 'EndpointSuffix=core.windows.net'
    return (
        f'{connection_str_before_key}AccountKey=accountKey;{connection_str_after_key}',
        f'{connection_str_before_key}AccountKey={CredentialScrubber.PLACE_HOLDER};{connection_str_after_key}',
    )


def mock_sas_uri():
    uri_without_signature = \
        'https://bloburi/containerName/file.txt?sv=2021-10-04&se=2023-05-17&sr=b&sp=rw'
    return (
        f'{uri_without_signature}&sig=signature',
        f'{uri_without_signature}&sig={CredentialScrubber.PLACE_HOLDER}'
    )


@pytest.mark.unittest
class TestCredentialScrubber:
    def test_scrub_sigature_in_sasuri(self):
        input_str, ground_truth = mock_sas_uri()
        assert CredentialScrubber().scrub(input_str) == ground_truth

    def test_scrub_key_in_connection_string(self):
        input_str, ground_truth = mock_connection_string()
        output = CredentialScrubber().scrub(input_str)
        assert output == ground_truth

    def test_add_regex(self):
        scrubber = CredentialScrubber()
        scrubber.add_regex(r'(?<=credential=)[^\s;&]+')
        assert scrubber.scrub('test&credential=credential') == f'test&credential={CredentialScrubber.PLACE_HOLDER}'

    def test_add_str(self):
        scrubber = CredentialScrubber()
        scrubber.add_str('credential')
        assert scrubber.scrub('test&secret=credential') == f'test&secret={CredentialScrubber.PLACE_HOLDER}'

    def test_add_str_length_threshold(self):
        """If the secret is too short (length <= 2 chars), it will not be scrubbed."""
        scrubber = CredentialScrubber()
        scrubber.add_str('yy')
        assert scrubber.scrub('test&secret=yy') == 'test&secret=yy'

    def test_normal_str_not_affected(self):
        assert CredentialScrubber().scrub('no secret') == 'no secret'
