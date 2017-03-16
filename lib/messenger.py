# -*- coding: utf-8 -*-

"""
Messenger

"""
# find the plugins


import time
import traceback

import msgpack
# from sys import version_info
# from redis.exceptions import ConnectionError, NoScriptError
from maboio.lib.influxdb_lib import InfluxC
from maboio.lib.redis_lib import RedisClient
from logbook import Logger

log = Logger('msger')


class Messenger(object):
    """   messenger """

    def __init__(self, conf, redis_address):
        """ init """

        self.interval = 1
        print(redis_address)
        self.red = RedisClient(redis_address)
        self.influxc = InfluxC(conf['influxdb'])
        self.dead_threshold = conf['app']['dead_threshold']
        self.node_name = conf['app']['node_name']
        self.int_tags = conf['app']['int_tags']

    def run(self):
        """ send msg to influxdb  """
        dead_count = 0
        last_alive_time = time.time()

        while True:
            if dead_count > 5:
                dead_json = {'time': int(time.time()) * 1000000,
                             'measurement': 'dead_node',
                             'fields': {'node_name': self.node_name},
                             'tags': {'alive?': 'no'}
                             }
                try:
                    self.influxc.send([dead_json])
                    log.debug('the node is dead now')
                except Exception as e:
                    log.error(e)
            try:
                data_len = self.red.get_len()
                if data_len > 0:
                    alive_json = {'time': int(time.time()) * 1000000,
                                  'measurement': 'dead_node',
                                  'fields': {'node_name': self.node_name},
                                  'tags': {'alive?': 'yes'}
                                  }
                    self.influxc.send([alive_json])
                    dead_count = 0
                    last_alive_time = time.time()
                    for i in range(0, data_len):

                        rdata = self.red.dequeue()
                        data = Messenger.transefer(msgpack.unpackb(rdata[1]))

                        data_handle = self.convert_float(data['data']['fields'])

                        data['data']['fields'] = data_handle

                        # log.debug(data)

                        # string to integer

                        data['data']['time'] = round(float(data['data']['time']))

                        json_data = [data['data']]

                        log.debug(json_data)

                        try:
                            self.influxc.send(json_data)
                        except Exception as ex:

                            log.error(ex)
                            log.error(traceback.format_exc())

                            log.debug("re queue...")
                            self.red.re_queue(rdata)
                            time.sleep(6)
                            continue
                else:
                    log.debug('queue now don\'t have data')
                    now = time.time()
                    threshold = self.dead_threshold * 1
                    if now - last_alive_time > threshold:
                        dead_count += 1

            except Exception as ex:
                log.error(ex)
                log.error(traceback.format_exc())

            # timer("output")
            time.sleep(self.interval)

    @staticmethod
    def transefer(bytes_dict):
        """
        lua to python3, lua's table will be transefer to python dict, but the key
        and the value of dict is byte string, and bytes string can't be directly
        used in send function from influxdb package.
        :param bytes_dict: a dict whcih key and value is byte string.
        :return: a user-friendly normal dict.
        """
        a = {}
        if not isinstance(bytes_dict, dict):
            return bytes_dict
        for key, value in bytes_dict.items():
            value = Messenger.transefer(value)
            if isinstance(key, bytes):
                key = key.decode()
            if isinstance(value, bytes):
                value = value.decode()
            a[key] = value
        return a

    def convert_float(self, data):
        """
        convert the int data to float data
        :param  data,allowed_tag
        :return :data we need
        """
        int_tags = self.int_tags

        data_handle = {}

        log.debug(data)

        for key, value in data.items():

            if (key not in int_tags) and (type(value) == int):

                data_handle[key] = float(value)

            else:
                data_handle[key] = value

        log.debug(data_handle)

        return data_handle
