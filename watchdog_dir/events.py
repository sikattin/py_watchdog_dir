# -*- coding: utf-8 -*-
import os
import re
import time
import sys
import glob
import shutil
import socket
import smtplib
from configparser import ConfigParser
from email.message import EmailMessage
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from mylogger.factory import RotationLoggerFactory


CONF_NAME = "watchdog_dir.conf"
LOGPATH = '/var/log/watchdog_dir.log'
SMTPHOST = '59.128.93.227'
EXT_SERVER_PATCH = ".server"
DST_PATH_TEST = r'/mnt/shared/test'
DST_PATH_PRE = r'/mnt/shared/pre'
REGEXP_TEST = '.+test'
REGEXP_PRE = '.+pre'

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
        self.logpath = config['LOG']['LOG_PATH']
        self.target_dir = target_dir
        self._logger = logger
        if self.logpath == '':
            self.logpath = LOGPATH
        if self._logger is None:
            if not os.path.isdir(os.path.dirname(self.logpath)):
                try:
                    os.mkdir()
                except:
                    print("can't create log directory.check error messages.")
            rotlogger_fac = RotationLoggerFactory(loglevel=loglevel)
            self._logger = rotlogger_fac.create(file=self.logpath, max_bytes=100000)
            print("write log in {}".format(self.logpath))

    def on_created(self, event):
        """[summary]
        
        Args:
            event ([type]): [description]
        """
        filename = os.path.basename(event.src_path)
        ext = os.path.splitext(filename)[1]
        self._logger.info("{0} has created on {1}".format(filename,
                                                          os.path.dirname(event.src_path))
        )
        print("ext: {}".format(ext))
        if ext == EXT_SERVER_PATCH:
            self.copy_server_patch(event.src_path)
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
            self._logger.info("failed to copy a file {0} to {1}".format(src_path, dst_path))
            # send mail
            self._send_mail("Failed to transfer a file {}".format(os.path.basename(src_path)),
                            "Failed to copy {0} to {1}".format(src_path, dst_path))
        else:
            self._logger.info("succeeded to copy a file {1} to {2}".format(src_path, dst_path))
            # send mail
            self._send_mail("Transferd {}".format(os.path.basename(src_path)),
                            "transfering process is ok.")
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
