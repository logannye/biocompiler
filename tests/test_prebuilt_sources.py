"""Source controls with inert streams and tar fixtures; no native work."""
from copy import deepcopy
import errno
import io
import json
from pathlib import Path
import ssl
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from tools import prebuilt_sources as sources


class Response(io.BytesIO):
    def __init__(self, raw, url):
        super().__init__(raw); self.url = url
    def geturl(self):
        return self.url


class SourceFetchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.url = sources.REVIEWED_URLS['gmp']
        self.mirror = sources.FALLBACKS[self.url][0]
        self.raw = b'inert source archive bytes: never extracted or executed'
        self.pin = {'size': len(self.raw), 'sha256': sources.release.sha(self.raw)}
        self.output = self.root / 'gmp.source'
        self.stream = io.StringIO()
        patches = [patch('sys.stdout', self.stream), patch.object(sources.time, 'sleep'),
                   patch.object(sources.subprocess, 'run', side_effect=AssertionError('No native process')),
                   patch.object(sources.subprocess, 'check_output', side_effect=AssertionError('No native process'))]
        for item in patches:
            item.start(); self.addCleanup(item.stop)

    def opened(self, outcomes):
        opener = unittest.mock.Mock()
        opener.open.side_effect = outcomes
        return opener

    def test_network_only_retry_then_verified_exact_mirror(self):
        error = urllib.error.URLError(OSError(errno.ENETUNREACH, 'secret=https://token.example/?password=secret'))
        opener = self.opened([error, Response(self.raw, self.mirror)])
        events = []
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
            result = sources.fetch(self.url, self.pin, self.output, source='gmp', notify=events.append)
        self.assertEqual([call.args[0] for call in opener.open.call_args_list], [self.url, self.mirror])
        self.assertTrue(all(call.kwargs == {'timeout': 12} for call in opener.open.call_args_list))
        self.assertEqual(result['selected_url'], self.mirror)
        self.assertEqual(result['attempt'], 1)
        self.assertEqual(self.output.read_bytes(), self.raw)
        self.assertFalse(self.output.with_suffix('.source.part').exists())
        self.assertEqual([row['status'] for row in events], ['started', 'network_error', 'started', 'verified'])
        self.assertNotIn('secret', self.stream.getvalue())
        self.assertNotIn('secret', json.dumps(events))

    def test_same_url_success_on_second_attempt(self):
        url = sources.REVIEWED_URLS['digestif']
        opener = self.opened([ConnectionResetError(errno.ECONNRESET, 'reset'), Response(self.raw, url)])
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
            selected = sources.fetch(url, self.pin, self.output)
        self.assertEqual(selected['selected_url'], url)
        self.assertEqual(selected['attempt'], 2)
        self.assertEqual(opener.open.call_count, 2)

    def test_all_network_failures_stop_after_two_attempts_per_reviewed_url(self):
        opener = self.opened([TimeoutError('secret')] * 5)
        events = []
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(sources.FetchError, 'bounded source network attempts failed'):
                sources.fetch(self.url, self.pin, self.output, notify=events.append)
        self.assertEqual(opener.open.call_count, 4)
        self.assertEqual([row['url'] for row in events if row['status'] == 'started'], [self.url, self.mirror] * 2)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix('.source.part').exists())

    def test_checksum_short_oversized_and_tls_mismatch_never_retry_or_fallback(self):
        cases = [Response(b'x' * len(self.raw), self.url), Response(self.raw[:-1], self.url), Response(self.raw + b'x', self.url),
                 Response(self.raw, 'http://mirror.example/archive'),
                 urllib.error.URLError(ssl.SSLCertVerificationError('secret certificate detail'))]
        for response in cases:
            with self.subTest(response=type(response).__name__):
                opener = self.opened([response, Response(self.raw, self.mirror)])
                events = []
                with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
                    with self.assertRaises(sources.FetchError):
                        sources.fetch(self.url, self.pin, self.output, notify=events.append)
                self.assertEqual(opener.open.call_count, 1)
                self.assertEqual(events[-1]['status'], 'rejected')
                self.assertFalse(self.output.exists())
                self.assertFalse(self.output.with_suffix('.source.part').exists())

    def test_https_redirect_handler_checks_every_hop_and_redacts_signed_query(self):
        handler = sources.HttpsRedirect()
        request = urllib.request.Request(self.url)
        for url in ('http://insecure.example/source', 'https://user:secret@mirror.example/source', 'ftp://mirror.example/source',
                    'https://mirror.example:444/source'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, 'redirect', {}, url)
        signed = 'https://release-assets.githubusercontent.com/path/source?signature=secret#fragment'
        redirected = handler.redirect_request(request, None, 302, 'redirect', {}, signed)
        self.assertEqual(redirected.full_url, signed)
        self.assertEqual(sources.public_url(signed), 'https://release-assets.githubusercontent.com/path/source')
        opener = self.opened([Response(self.raw, signed)])
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
            sources.fetch(self.url, self.pin, self.output)
        self.assertNotIn('secret', self.stream.getvalue())

    def test_no_unreviewed_url_or_false_source_name(self):
        for url, name in (('https://arbitrary.example/gmp.tar.xz', 'gmp'), (self.url, 'dune')):
            with patch.object(sources.urllib.request, 'build_opener', side_effect=AssertionError('must not contact network')):
                with self.assertRaises(ValueError):
                    sources.fetch(url, self.pin, self.output, source=name)
        self.assertEqual(set(sources.FALLBACKS), {sources.REVIEWED_URLS['gmp']})
        self.assertEqual(sources.FALLBACKS[self.url], ('https://mirrors.kernel.org/gnu/gmp/gmp-6.3.0.tar.xz',))

    def test_existing_destination_partial_and_racing_destination_never_overwritten(self):
        for path in (self.output, self.output.with_suffix('.source.part')):
            path.write_bytes(b'preexisting')
            with patch.object(sources.urllib.request, 'build_opener', side_effect=AssertionError('must not contact network')):
                with self.assertRaises((ValueError, sources.FetchError)):
                    sources.fetch(self.url, self.pin, self.output)
            self.assertEqual(path.read_bytes(), b'preexisting'); path.unlink()
        real_link = sources.os.link
        def racing_link(source, destination):
            destination.write_bytes(b'concurrent owner')
            return real_link(source, destination)
        opener = self.opened([Response(self.raw, self.url)])
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener), patch.object(sources.os, 'link', side_effect=racing_link):
            with self.assertRaises(sources.FetchError):
                sources.fetch(self.url, self.pin, self.output)
        self.assertEqual(self.output.read_bytes(), b'concurrent owner')
        self.assertFalse(self.output.with_suffix('.source.part').exists())

    def test_nonnetwork_local_write_and_http_not_found_fail_without_retry(self):
        for error in (PermissionError(errno.EACCES, 'private path'), urllib.error.HTTPError(self.url, 404, 'secret', {}, None)):
            opener = self.opened([error])
            with patch.object(sources.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(sources.FetchError):
                    sources.fetch(self.url, self.pin, self.output)
            self.assertEqual(opener.open.call_count, 1)
        error = urllib.error.HTTPError(self.url, 503, 'unavailable', {}, None)
        try:
            self.assertTrue(sources.network_failure(error))
        finally:
            error.close()

    def fake_lock(self):
        lock = json.loads(sources.LOCK.read_bytes())
        for row in lock['sources'].values():
            row.update(self.pin)
        return lock

    def test_failure_receipt_retains_verified_prefix_all_attempts_and_original_pins(self):
        lock = self.fake_lock(); output = self.root / 'sources'
        names = list(lock['sources'])
        opener = self.opened([Response(self.raw, lock['sources'][names[0]]['url']), TimeoutError('secret'), TimeoutError('secret')])
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener), \
             patch.object(sources, 'inspect_sources', side_effect=AssertionError('cannot inspect incomplete collection')):
            with self.assertRaises(sources.FetchError):
                sources.fetch_sources(lock, output)
        receipt = json.loads((output / 'fetch-receipt.json').read_bytes())
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(set(receipt['completed']), {names[0]})
        self.assertEqual([row['status'] for row in receipt['attempts']], ['verified', 'network_error', 'network_error'])
        self.assertEqual(receipt['sources'], {name: {key: row[key] for key in ('url', 'path', 'sha256', 'size')} for name, row in lock['sources'].items()})
        self.assertEqual(receipt['lock_sha256'], sources.release.sha(sources.release.canonical(lock)))
        self.assertNotIn('secret', json.dumps(receipt))
        self.assertFalse((output / 'source-receipt.json').exists())

    def test_success_preserves_original_source_notice_receipt_shape(self):
        lock = self.fake_lock(); output = self.root / 'sources'
        original = deepcopy(lock)
        opener = self.opened([Response(self.raw, row['url']) for row in lock['sources'].values()])
        legacy = {name: {'source': self.pin, 'notices': row['notices']} for name, row in lock['sources'].items()}
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener), patch.object(sources, 'inspect_sources', return_value=legacy) as inspect:
            receipt = sources.fetch_sources(lock, output)
        self.assertEqual(lock, original)
        inspect.assert_called_once_with(lock, output)
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(set(receipt['completed']), set(lock['sources']))
        self.assertEqual(json.loads((output / 'source-receipt.json').read_bytes()), legacy)
        self.assertEqual(json.loads((output / 'fetch-receipt.json').read_bytes()), receipt)

    def test_elapsed_stream_guard_withholds_output_without_fallback(self):
        opener = self.opened([Response(self.raw, self.url)])
        with patch.object(sources.urllib.request, 'build_opener', return_value=opener), patch.object(sources.time, 'monotonic', side_effect=[0, 31]):
            with self.assertRaises(sources.FetchError):
                sources.fetch(self.url, self.pin, self.output)
        self.assertEqual(opener.open.call_count, 1)
        self.assertFalse(self.output.exists())

    def test_delayed_eof_is_checked_before_publication_without_fallback(self):
        original_pin = deepcopy(self.pin)
        for eof_time in (30, 31):
            with self.subTest(eof_time=eof_time):
                response = Response(self.raw, self.url)
                opener = self.opened([response])
                events = []
                with patch.object(sources.urllib.request, 'build_opener', return_value=opener), \
                     patch.object(sources.time, 'monotonic', side_effect=[0, 1, 2, 29, eof_time]), \
                     patch.object(response, 'read1', wraps=response.read1) as read:
                    if eof_time == 30:
                        sources.fetch(self.url, self.pin, self.output, notify=events.append)
                        self.assertEqual(self.output.read_bytes(), self.raw)
                        self.output.unlink()
                    else:
                        with self.assertRaises(sources.FetchError):
                            sources.fetch(self.url, self.pin, self.output, notify=events.append)
                        self.assertEqual([row['status'] for row in events], ['started', 'rejected'])
                        self.assertFalse(self.output.exists())
                    self.assertEqual(read.call_count, 2)
                self.assertEqual(opener.open.call_count, 1)
                self.assertFalse(self.output.with_suffix('.source.part').exists())
                self.assertEqual(self.pin, original_pin)


class SourceExtractionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / 'inert.tar'
        self.output = self.root / 'extracted'
        for item in (
            patch.object(sources.subprocess, 'run', side_effect=AssertionError('No native process')),
            patch.object(sources.subprocess, 'Popen', side_effect=AssertionError('No child process')),
            patch.object(sources.urllib.request, 'build_opener', side_effect=AssertionError('No network')),
        ):
            item.start(); self.addCleanup(item.stop)

    @staticmethod
    def member(name, data=b'inert source data', *, mtime=1_700_000_000, mode=0o644,
               kind=tarfile.REGTYPE, linkname=''):
        entry = tarfile.TarInfo(name)
        entry.type, entry.mtime, entry.mode, entry.linkname = kind, mtime, mode, linkname
        entry.size = len(data) if kind == tarfile.REGTYPE else 0
        return entry, data

    def write_archive(self, members):
        with tarfile.open(self.archive, 'w', format=tarfile.PAX_FORMAT) as archive:
            for entry, data in members:
                archive.addfile(entry, io.BytesIO(data) if entry.isfile() else None)

    def test_generated_manual_keeps_newer_archive_time_when_stored_before_its_input(self):
        self.write_archive([
            self.member('package/doc/manual.info', b'generated manual\n', mtime=1_700_000_200),
            self.member('package/configure', b'inert executable text\n', mtime=1_700_000_100, mode=0o755),
            self.member('package/doc/manual.texi', b'manual input\n', mtime=1_700_000_000),
        ])
        package = sources.extract_source(self.archive, self.output)
        self.assertEqual(package, self.output / 'package')
        for name, data, timestamp, mode in (
            ('doc/manual.info', b'generated manual\n', 1_700_000_200, 0o644),
            ('configure', b'inert executable text\n', 1_700_000_100, 0o755),
            ('doc/manual.texi', b'manual input\n', 1_700_000_000, 0o644),
        ):
            with self.subTest(name=name):
                path = package / name
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(path.stat().st_mtime_ns, timestamp * 1_000_000_000)
                self.assertEqual(path.stat().st_mode & 0o777, mode)
        # This is make's dependency-age condition, checked without running make.
        self.assertGreater((package / 'doc/manual.info').stat().st_mtime_ns,
                           (package / 'doc/manual.texi').stat().st_mtime_ns)

    def test_unsafe_paths_duplicates_and_special_members_remain_rejected(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'preserved outside file')
        cases = (
            [self.member('../outside')],
            [self.member(str(outside))],
            [self.member('package/../outside')],
            [self.member('package/same'), self.member('./package/same')],
            [self.member('package/device', kind=tarfile.CHRTYPE)],
            [self.member('package/fifo', kind=tarfile.FIFOTYPE)],
        )
        for index, members in enumerate(cases):
            with self.subTest(index=index):
                self.write_archive(members)
                output = self.root / f'rejected-{index}'
                with self.assertRaises(ValueError):
                    sources.extract_source(self.archive, output)
                self.assertEqual(outside.read_bytes(), b'preserved outside file')
                self.assertFalse(any(output.rglob('*')))

    def test_exact_supported_timestamp_boundaries_and_fraction_are_preserved(self):
        self.write_archive([
            self.member('package/epoch', mtime=0),
            self.member('package/latest', mtime=4_294_967_295),
            self.member('package/fraction', mtime=1_700_000_000.5),
        ])
        package = sources.extract_source(self.archive, self.output)
        for name, expected_ns in (
            ('epoch', 0),
            ('latest', 4_294_967_295_000_000_000),
            ('fraction', 1_700_000_000_500_000_000),
        ):
            with self.subTest(name=name):
                self.assertEqual((package / name).stat().st_mtime_ns, expected_ns)

    def test_invalid_archived_times_reject_before_any_member_is_written(self):
        for index, timestamp in enumerate(('-1', '4294967296', 'nan', 'inf', '-inf')):
            with self.subTest(timestamp=timestamp):
                invalid = self.member('package/invalid', mtime=0)
                invalid[0].pax_headers = {'mtime': timestamp}
                self.write_archive([
                    self.member('package/first', mtime=1_700_000_000),
                    invalid,
                ])
                output = self.root / f'time-rejected-{index}'
                with self.assertRaisesRegex(ValueError, 'timestamp'):
                    sources.extract_source(self.archive, output)
                self.assertFalse(any(output.rglob('*')))

    def test_copied_hardlink_keeps_own_time_without_retiming_source_through_symlink(self):
        self.write_archive([
            self.member('package/source', b'original content', mtime=1_700_000_200),
            self.member('package/copy', kind=tarfile.LNKTYPE, linkname='package/source', mtime=1_700_000_100),
            self.member('package/symlink', kind=tarfile.SYMTYPE, linkname='source', mtime=1_700_000_000),
        ])
        package = sources.extract_source(self.archive, self.output)
        original, copied, link = package / 'source', package / 'copy', package / 'symlink'
        self.assertEqual(original.read_bytes(), b'original content')
        self.assertEqual(copied.read_bytes(), b'original content')
        self.assertFalse(copied.is_symlink())
        self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)
        self.assertEqual(original.stat().st_mtime_ns, 1_700_000_200_000_000_000)
        self.assertEqual(copied.stat().st_mtime_ns, 1_700_000_100_000_000_000)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), Path('source'))
        self.assertEqual(link.read_bytes(), b'original content')

    def test_escaping_links_and_members_below_links_remain_rejected(self):
        cases = (
            [self.member('package/link', kind=tarfile.SYMTYPE, linkname='/outside')],
            [self.member('package/link', kind=tarfile.SYMTYPE, linkname='../../outside')],
            [self.member('package/link', kind=tarfile.LNKTYPE, linkname='/outside')],
            [self.member('package/link', kind=tarfile.LNKTYPE, linkname='../outside')],
            [self.member('package/link/child'),
             self.member('package/link', kind=tarfile.SYMTYPE, linkname='safe')],
            [self.member('package/link/child'),
             self.member('package/link', kind=tarfile.LNKTYPE, linkname='package/safe')],
        )
        for index, members in enumerate(cases):
            with self.subTest(index=index):
                self.write_archive(members)
                output = self.root / f'link-rejected-{index}'
                with self.assertRaises(ValueError):
                    sources.extract_source(self.archive, output)
                self.assertFalse(any(output.rglob('*')))

    def test_indirect_symlink_parent_cannot_supply_an_external_hardlink_source(self):
        outside = self.root / 'outside'
        outside.mkdir()
        marker = outside / 'marker'
        marker.write_bytes(b'inert external marker')
        original_stat = marker.stat()
        self.write_archive([
            self.member('package', kind=tarfile.DIRTYPE),
            self.member('package/a', kind=tarfile.SYMTYPE, linkname='..'),
            self.member('package/c', kind=tarfile.SYMTYPE, linkname='a/../outside'),
            self.member('package/copied', kind=tarfile.LNKTYPE, linkname='package/c/marker'),
        ])
        with self.assertRaises(ValueError):
            sources.extract_source(self.archive, self.output)
        self.assertFalse((self.output / 'package/copied').exists())
        self.assertEqual(marker.read_bytes(), b'inert external marker')
        self.assertEqual(marker.stat().st_mtime_ns, original_stat.st_mtime_ns)

    def test_forward_hardlink_to_indexed_regular_member_preserves_bytes_and_times(self):
        self.write_archive([
            self.member('package/copied', kind=tarfile.LNKTYPE, linkname='package/source', mtime=1_700_000_100),
            self.member('package/source', b'inert forward target', mtime=1_700_000_200),
        ])
        package = sources.extract_source(self.archive, self.output)
        self.assertEqual((package / 'copied').read_bytes(), b'inert forward target')
        self.assertFalse((package / 'copied').is_symlink())
        self.assertEqual((package / 'copied').stat().st_mtime_ns, 1_700_000_100_000_000_000)
        self.assertEqual((package / 'source').stat().st_mtime_ns, 1_700_000_200_000_000_000)


if __name__ == '__main__':
    unittest.main()
