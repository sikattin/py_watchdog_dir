# -*- coding: utf-8 -*-
import os
import re
import time
import sys
import glob
import shutil
import socket
import smtplib
import hashlib
from configparser import ConfigParser
from email.message import EmailMessage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from mylogger.factory import RotationLoggerFactory


LOG_FILE = "/var/log/vsftpd.log"
CONF_NAME = "watchdog_dir.conf"
LOGPATH = '/var/log/watchdog_dir.log'
SMTPHOST = '59.128.93.227'
EXT_SERVER_PATCH = ".server"
DST_PATH_TEST = r'/mnt/shared/test'
DST_PATH_PRE = r'/mnt/shared/pre'
REGEXP_TEST = '.+/test/.+'
REGEXP_PRE = '.+/pre/.+'
BASESIZE_READ = 4096

class FTPEventHandler(FileSystemEventHandler):
    """イベントハンドラ
    
    Args:
        FileSystemEventHandler ([type]): [description]
    """
    def __init__(self,
                 target_dir,
                 logger=None,
                 loglevel=20,
                 **config
        ):
        """constructor
        
        Args:
            target_dir (str): target directory to observe.
            logger (optional): Defaults to None: logger object.
            loglevel (int, optional): Defaults to 20: loglevel of logging.
            config (dict): configure values
        """

        super(FTPEventHandler, self).__init__()
        self._config = config
        if len(self._config) == 0:
            self._config['MAIL']['FROM'] = ''
            self._config['MAIL']['TO'] = ''
            self._config['MAIL']['CC'] = ''
            self._config['MAIL']['SMTP_HOST'] = SMTPHOST
            self._config['LOG']['LOG_PATH'] = LOGPATH
            self._config['GENERAL']['WATCH_LOG'] = ''
        # log file
        try:
            self.logpath = self._config['LOG']['LOG_PATH']
        except KeyError:
            self.logpath = LOGPATH
        else:
            if self.logpath == '':
                self.logpath = LOGPATH
        # target log file for watching 
        try:
            self.watchlog = self._config['GENERAL']['WATCH_LOG']
        except KeyError:
            self.watchlog = ''
        # target directory for watching
        self.target_dir = target_dir
        # setup logger
        self._logger = logger
        if self._logger is None:
            if not os.path.isdir(os.path.dirname(self.logpath)):
                try:
                    os.mkdir()
                except:
                    print("can't create log directory.check error messages.")
                    raise
            rotlogger_fac = RotationLoggerFactory(loglevel=loglevel)
            self._logger = rotlogger_fac.create(file=self.logpath, max_bytes=100000)
            print("write log in {}".format(self.logpath))

    def on_created(self, event):
        """[summary]
        
        Args:
            event ([type]): [description]
        """
        filesize = os.path.getsize(event.src_path)
        filename = os.path.basename(event.src_path)
        ext = os.path.splitext(filename)[1]
        self._logger.info("{0} has created on {1}".format(filename,
                                                          os.path.dirname(event.src_path))
        )
        if ext == EXT_SERVER_PATCH:
            time.sleep(2)
            while True:
                # check difference of file size.
                # if file size is equal, consider the file uploaded.
                if filesize == os.path.getsize(event.src_path):
                    try:
                        # parsing log file, get file size uploaded it.
                        with open(self.watchlog) as f:
                            lines = f.readlines()
                            for line in lines[::-1]:
                                # 正規表現を修正する
                                # re.search(r"(OK UPLOAD.+{}\", )([0-9]+ bytes)", line)
                                match = re.search(r"(OK UPLOAD.+{}\", )([0-9]+ bytes)".format(filename), line)
                                if match is not None:
                                    file_bytesize = match.group(2).split()[0]
                                    self._logger.debug("result of parsing log file: {} bytes".format(file_bytesize))
                                    # break for statement.
                                    break
                    except Exception as e:
                        self._logger.warning("raise error while parsing log file."
                                           "target log file path: {0}\n"
                                           "reason: {1}".format(self.watchlog, e))
                        time.sleep(1)
                        # copy server patch to specified directory
                        self.copy_server_patch(event.src_path)
                        # break while statement
                        break
                    else:
                        # compare file size on local with written it in log file.
                        for i in range(0, 5):
                            # when file size is equal.
                            if os.path.getsize(event.src_path) == int(file_bytesize):
                                self._logger.info("{0} has completely uploaded. "
                                                "file size is {1} bytes"
                                                .format(event.src_path, file_bytesize))
                                # copy server patch to specified directory
                                self.copy_server_patch(event.src_path)
                                # break for statement of else clause.
                                break
                            # when file size is not equal.
                            else:
                                self._logger.warning("{0} has uploaded."
                                                    "but it may not be completely uploaded."
                                                    "uploaded file size={1} bytes, "
                                                    "file size result of parsing log file={2} bytes."
                                                    .format(event.src_path, os.path.getsize(event.src_path), file_bytesize))
                                time.sleep(1)
                                # continue for statement of else clause.
                                continue
                        # break while statement.
                        break
                # file size is not equal
                else:
                    self._logger.info("{} is uploading now...".format(event.src_path))
                    filesize = os.path.getsize(event.src_path)
                    time.sleep(2)
                    continue
        print("ファイル {} が作成されました。".format(filename))

    def on_modified(self, event):
        """[summary]
        
        Args:
            event ([type]): [description]
        """

        filepath = event.src_path
        filename = os.path.basename(filepath)
        print("ファイル {} が変更されました。".format(filename))

    def on_deleted(self, event):
        """[summary]
        
        Args:
            event ([type]): [description]
        """
        filepath = event.src_path
        filename = os.path.basename(filepath)
        print("ファイル {} が削除されました。".format(filename))

    def on_moved(self, event):
        """[summary]
        
        Args:
            event ([type]): [description]
        """
        filepath = event.src_path
        filename = os.path.basename(filepath)
        print("ファイル {0} が {1} に移動しました。".format(filename, event.dst_path))

    def calc_md5sum_of_fileobj(self, path: str):
        """[summary]
        
        Args:
            path (str): file path
        
        Returns:
            int: md5 check sum
        """
        md5 = hashlib.md5()
        with open(path, mode='rb') as f:
            for chunk in iter(lambda: f.read(BASESIZE_READ * md5.block_size), b''):
                md5.update(chunk)
        checksum = md5.hexdigest()
        return checksum

    def copy_server_patch(self, src_path: str):
        """transfer server patch to the specified directory.
        
        Args:
            src_path (str): source path of copy targeted file.
        """
        dst_path = ''
        if re.match(REGEXP_TEST, src_path):
            dst_path = DST_PATH_TEST
        elif re.match(REGEXP_PRE, src_path):
            dst_path = DST_PATH_PRE
        try:
            shutil.copy(src_path, dst_path)
        except:
            self._logger.info("Failed to copy a file {0} to {1}".format(src_path, dst_path))
            # send mail
            self._send_mail("Failed to transfer a file {}".format(os.path.basename(src_path)),
                            "Failed to copy {0} to {1}".format(src_path, dst_path))
        else:
            self._logger.info("Succeeded to copy a file {0} to {1}".format(src_path, dst_path))
            filename = os.path.basename(src_path)
            # calc md5 checksum
            result = self.calc_md5sum_of_fileobj(os.path.join(dst_path, filename))
            # send mail
            self._send_mail("{0} was transferd to {1}".format(filename, dst_path),
                            "Src_path(ftp server): {0}\r\n"
                            "Dst_path(mount directory): {1}\r\n"
                            "MD5: {2}".format(src_path, dst_path, result))
            return (src_path, dst_path)

    def _send_mail(self, subject: str, mailbody: str):
        """send mail
        
        Args:
            subject (str): Subject of mail
            mailbody (str): Body of mail
        """
        with smtplib.SMTP(self._config['MAIL']['SMTP_HOST']) as smtp:
            smtp.ehlo()
            msg = EmailMessage()
            msg.set_content(mailbody)
            msg['Subject'] = '[watchdog_dir] {}'.format(subject)
            msg['From'] = self._config['MAIL']['FROM']
            msg['To'] = self._config['MAIL']['TO']
            msg['Cc'] = self._config['MAIL']['CC']
            try:
                result = smtp.send_message(msg)
            except smtplib.SMTPRecipientsRefused as smtp_refuse_e:
                recipients = [key for key in smtp_refuse_e.recipients.keys()]
                self._logger.error("The mail was not sent to {}".format(', '.join(recipients)))
            except smtplib.SMTPHeloError:
                self._logger.error("SMTP Server does not replied against HELO.")
            except smtplib.SMTPSenderRefused:
                self._logger.error("SMTP Server does not recieved {}".format(self._config['MAIL']['FROM']))
            except smtplib.SMTPDataError:
                self._logger.error("SMTP Server does responsed illegular error code.")
            except smtplib.SMTPNotSupportedError:
                self._logger.error("SMTP Server does not support 'SMTPUTF8'")
            except Exception as e:
                self._logger.error("Raise uncached error {}".format(e))
            else:
                self._logger.info("Send mail.")
                return result
