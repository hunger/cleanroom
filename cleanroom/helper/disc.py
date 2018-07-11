# -*- coding: utf-8 -*-
"""Helpers for handling discs and partitions.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from .run import run

from ..printer import (verbose, debug, trace)

import collections
import json
import math
import os
import os.path
import stat
from time import sleep


Disk = collections.namedtuple('Disk', ['label', 'id', 'device', 'unit', 'firstlba', 'lastlba', 'partitions'])
Partition = collections.namedtuple('Partition', ['node', 'start', 'size', 'type', 'uuid', 'name'])


def _is_root():
    return os.geteuid() == 0


def is_block_device(path):
    try:
        stat_info = os.stat(path)
        return stat.S_ISBLK(stat_info.st_mode)
    except os.error:
        return False


def _command(command, fallback):
    result = fallback if command is None else command
    assert os.path.isfile(result)
    assert os.access(result, os.X_OK)

    return result


def _qemu_img(command):
    return _command(command, '/usr/bin/qemu-img')


def _qemu_nbd(command):
    return _command(command, '/usr/bin/qemu-nbd')


def _sfdisk(command):
    return _command(command, '/usr/bin/sfdisk')


def quantify(size, block_size):
    if size is None:
        return None

    quant_size = math.floor(size / block_size)
    if quant_size * block_size != size:
        quant_size += 1
    return quant_size * block_size


def kib_ify(size):
    return quantify(size, 1024)


def mib_ify(size):
    return quantify(size, 1024 * 1024)


def normalize_size(size):
    if size is None:
        return None

    if isinstance(size, int):
        return size

    factor = 1
    if isinstance(size, str):
        unit = size[-1:].lower()
        number_string = size[:-1]
        if unit == 'b':
            pass
        elif unit == 'k':
            factor = 1024
        elif unit == 'm':
            factor = 1024 * 1024
        elif unit == 'g':
            factor = 1024 * 1024 * 1024
        elif unit == 't':
            factor = 1024 * 1024 * 1024 * 1024
        elif '0' <= unit <= '9':
            number_string += unit
        else:
            raise ValueError()

        number = int(number_string)
        if number < 0:
            raise ValueError()

        return number * factor


def _sfdisk_size(size):
    if size is None:
        return None

    assert isinstance(size, int)
    return '{}KiB'.format(kib_ify(size) / 1024)


def create_image_file(file_name, size, *, disk_format='qcow2', command=None):
    assert _is_root()
    run(_qemu_img(command), 'create',
        '-q', '-f', disk_format, file_name, str(normalize_size(size)))


class Device:
    def __init__(self, device):
        assert is_block_device(device)
        self._device = device

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def device(self, partition=None):
        if partition is None:
            return self._device
        return '{}{}'.format(self._device, partition)

    def close(self):
        pass

    def wait_for_device_node(self, partition=None):
        dev = self.device(partition)
        trace('Waiting for "{}".'.format(dev))
        for i in range(10):
            if is_block_device(dev):
                return True
            sleep(0.1)
            trace('.')
        return False


class NbdDevice(Device):
    @staticmethod
    def NewImageFile(file_name, size, *, disk_format='qcow2',
                     command=None, qemu_img_command=None):
        create_image_file(file_name, size, disk_format=disk_format,
                          command=qemu_img_command)
        debug('New image file {} ({}) created with size {}.'
              .format(file_name, disk_format, size))
        return NbdDevice(file_name, disk_format=disk_format, command=command)

    def __init__(self, file_name, *, disk_format='qcow2', command=None):
        assert os.path.isfile(file_name)

        self._command = command
        self._file_name = file_name
        self._disk_format = disk_format

        super().__init__(self._create_nbd_block_device(file_name, disk_format=disk_format,
                                                       command=command))

        debug('Block device "{}" created for file {}.'.format(self._device, self._file_name))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self._device is not None:
            self._delete_nbd_block_device(self._device)
            self._device = None

    def device(self, partition=None):
        if partition is None:
            return self._device
        return '{}p{}'.format(self._device, partition)

    def disk_format(self):
        return self._disk_format

    def file_name(self):
        return self._file_name

    # Helpers:
    @staticmethod
    def _nbd_device(counter):
        return '/dev/nbd' + str(counter)

    @staticmethod
    def _create_nbd_block_device(file_name, *, disk_format='qcow2', command=None):
        assert _is_root()
        assert os.path.isfile(file_name)

        if not is_block_device(NbdDevice._nbd_device(0)):
            trace('Loading nbd kernel module...')
            run('/usr/bin/modprobe', 'nbd')

        for counter in range(257):
            device = NbdDevice._nbd_device(counter)
            if not is_block_device(device):
                trace('{} is not a block device, aborting'.format(device))
                return None

            result = run(_qemu_nbd(command), '--connect={}'.format(device),
                         '--format={}'.format(disk_format), file_name,
                         returncode=None)
            if result.returncode == 0:
                trace('Device {} connected to file {}.'.format(device, file_name))
                return device

            counter += 1

        trace('Too many nbd devices found, aborting!')
        return None

    @staticmethod
    def _delete_nbd_block_device(device, command=None):
        assert _is_root()
        assert is_block_device(device)

        run(_qemu_nbd(command), '--disconnect', device)
        trace('"{}" disconnected.'.format(device))


class Partitioner:
    def __init__(self, device, *, command=None):
        assert _is_root()
        assert is_block_device(device.device())

        self._command = command
        self._device = device
        self._data = None

        self._get_partition_data()

    @staticmethod
    def swap_partition(*, start=None, size='4G', name='swap partition'):
        return Partition(node=None,
                         start=start,
                         size=size,
                         uuid=None,
                         type='0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
                         name=name)

    @staticmethod
    def efi_partition(*, start=None, size='512M'):
        return Partition(node=None,
                         start=start,
                         size=size,
                         uuid=None,
                         type='c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
                         name='EFI System Partition')

    @staticmethod
    def data_partition(*, start=None, size=None,
                       type='2d212206-b0ee-482e-9fec-e7c208bef27a', name):
        return Partition(node=None,
                         start=start,
                         size=size,
                         uuid=None,
                         type=type,
                         name=name)

    def is_partitioned(self):
        return self._data is not None

    def device(self):
        return self._device

    def label(self):
        if self._data is None:
            return None
        return self._data.label

    def id(self):
        if self._data is None:
            return None
        return self._data.id

    def first_lba(self):
        if self._data is None:
            return None
        return self._data.firstlba

    def last_lba(self):
        if self._data is None:
            return None
        return self._data.lastlba

    def partitions(self):
        if self._data is None:
            return []
        return self._data.partitions

    def repartition(self, partitions):
        instructions = 'label: gpt\n'
        for p in partitions:
            assert isinstance(p, Partition)

            prefix = ''
            partition_data = []
            if p.node is not None:
                prefix = '{}: '.format(p.node)
            if p.start is not None:
                partition_data.append('start={}'.format(_sfdisk_size(normalize_size(p.start))))
            if p.size is not None:
                partition_data.append('size={}'.format(_sfdisk_size(normalize_size(p.size))))
            if p.type is not None:
                partition_data.append('type="{}"'.format(p.type))
            if p.uuid is not None:
                partition_data.append('uuid="{}"'.format(p.uuid))
            if p.name is not None:
                partition_data.append('name="{}"'.format(p.name))

            instructions += prefix + ', '.join(partition_data) + '\n'

        run('/usr/bin/flock', self._device.device(),
            _sfdisk(self._command), '--color=never', self._device.device(),
            input=instructions.encode('utf-8'))

        for i in range(len(partitions)):
            assert self._device.wait_for_device_node(partition=i+1)

        self._get_partition_data()

    def _get_partition_data(self):
        # FIXME: The sizes/start information is pretty useless.
        #        It is given in sectors, but there is no information
        #        how big such a sector actually is. Assuming 512 bytes
        #        no longer seems safe with 4K sector drives...
        result = run('/usr/bin/flock', self._device.device(),
                     _sfdisk(self._command), '--color=never',
                     '--json', self._device.device(), returncode=None)
        if result.returncode != 0:
            self._data = None
        else:
            json_data = json.loads(result.stdout)
            self._data = Disk(**json_data['partitiontable'])
            assert self._data.device == self._device.device()