# -*- coding: utf-8 -*-

"""
ChiTu main

ChiTu is the horse

"""

from __future__ import absolute_import

import os
import sys
import time

from maboio.lib.setup_logger import setup_logger
from maboio.lib.opts import get_option_parser
from maboio.lib.utils import get_conf

from lib.messenger import Messenger

import threading

from logbook import Logger

import psutil

import subprocess

# find the plugins
sys.path.append(os.getcwd())

log = Logger('main')


def main():
    """
    Multi-threaded crawling redis data sent to influxdb
    """

    appname = "chitu"

    parser = get_option_parser(appname)
    options, args = parser.parse_args()

    conf_file = os.path.abspath(options.config)

    conf = get_conf(conf_file)

    setup_logger(conf['logging'])

    log.debug("start...")

    thread_set = set()

    thread_name_set = set()

    # messenger who send msg to influxdb
    for redis_address in conf['redis']['address']:
        messenger = Messenger(conf, redis_address)

        thread_name = 'redis_' + str(redis_address['db'])

        if thread_name in thread_name_set:
            raise Exception('threat name exists')
        else:
            thread_name_set.add(thread_name)

        # messenger.run()
        t_worker = threading.Thread(target=messenger.run, name=thread_name, args=[])
        t_worker.setDaemon(True)
        t_worker.start()

        thread_set.add(thread_name)

    t_watchdog = threading.Thread(target=watchdog, name='watchdog', args=[thread_set])
    t_watchdog.setDaemon(True)
    t_watchdog.start()

    if conf['Deamon']['deamon']:
        deamon(conf['Deamon']['process_name'], conf['Deamon']['cmd'])


def watchdog(redis_threads):
    '''
    watch threads and daemon it
    :param redis_threads:
    :return: None
    '''
    while True:
        threads = set()
        for item in threading.enumerate():
            threads.add(item.name)

        log.debug("###" * 20)
        log.debug(redis_threads)
        log.debug(threads)

        if threads - {'watchdog', 'MainThread'} != redis_threads:
            dead_threads = redis_threads - (threads - {'watchdog', 'MainThread'})
            conf_file = os.path.abspath('conf/chitu.toml')
            conf = get_conf(conf_file)
            addresses = conf['redis']['address']
            for dead_thread in dead_threads:
                address = [i for i in addresses if i['db'] == dead_thread[-1]][0]
                thread_name = 'redis_' + str(address['db'])
                messenger = Messenger(conf, address)
                t_worker = threading.Thread(target=messenger.run, name=thread_name, args=[])
                t_worker.setDaemon(True)
                t_worker.start()

        time.sleep(10)


def deamon(task, cmd):
    '''
    Daemon, detect ziyan operation. If it die, reboot.
    once an hour
    :return: None
    '''

    while True:
        time.sleep(60 * 60)
        all_proc = (i.name() for i in psutil.process_iter())
        if task in all_proc:
            log.info('%s exists' % task)
        else:
            a = subprocess.Popen(cmd)
            log.info('%s was dead, startup ziyan' % task)


if __name__ == '__main__':
    main()
    while True:
        time.sleep(1)
