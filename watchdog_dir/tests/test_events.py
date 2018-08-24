# -*- coding: utf-8 -*-
import unittest
import tempfile
from watchdog_dir import events

CONFIG = {
          'MAIL':
              {
                  'FROM': 'test@local',
                  'TO': 'shikano.takeki@nexon.co.jp',
                  'CC': 'shikano.takeki@nexon.co.jp',
                  'SMTP_HOST': '59.128.93.227'
              },
          'LOG':
              {
                  'LOG_PATH': ''
              }
}


class TestFTPEventHandler(unittest.TestCase):
    """Testcase FTPEventHandler Class 
    
    Args:
        unittest ([type]): [description]
    """

    def setUp(self):
        self._ftph = events.FTPEventHandler('/tmp', **CONFIG)

    def tearDown(self):
        del self._ftph

    def test__send_mail(self):
        mail_subject = 'Test _send_mail()'
        mail_body = 'Test _send_mail() is OK!\nthis line is written on second line.'
        result = self._ftph._send_mail(mail_subject, mail_body)
        self.assertEqual(0, len(result))

    def test_copy_server_patch(self):
        tmpfile= tempfile.NamedTemporaryFile()
        src_path = tmpfile.name
        result = self._ftph.copy_server_patch(src_path)
        self.assertTrue(result)

