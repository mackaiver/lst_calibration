import numpy as np
import pandas as pd
from copy import deepcopy

from .utils import sample2cell

def read_calib_constants(filepath):
    return pd.read_hdf(filepath).set_index(
            ['pixel', 'channel', 'cell']
        ).sort_index()


class TimelapseCalibration:

    def __init__(self, filename):
        self.calib_constants = read_calib_constants(filename)
        self.roi = None
        self.sample = None

    def offset(self, delta_t, a, b, c):
        o = a * delta_t ** b + c
        o[np.isnan(o)] = c
        o[np.isnan(o)] = 0

        return o

    def __call__(self, event):
        ''' calibrate data in event '''
        event = deepcopy(event)

        if self.roi is None:
            self.roi = event.roi
            self.sample = np.arange(event.roi)

        assert self.roi == event.roi

        for pixel in range(len(event.data)):
            for channel in event.data.dtype.names:
                sc = event.header.stop_cells[pixel][channel]
                cells = sample2cell(self.sample, sc)

                dt = event.time_since_last_readout[pixel][channel]
                c = self.calib_constants.loc[pixel, channel].loc[cells]
                event.data[pixel][channel] -= self.offset(dt, c['a'], c['b'], c['c']).astype('>i2')

        return event

def read_offsets(offsets_file):
    offsets = np.zeros(
            shape=(8, 2, 4096, 40),
            dtype='f4')

    def name_to_channel_gain_id(name):
        _, channel, gain = name.split('_')
        channel = int(channel)
        gain_id = {'high':0, 'low':1}[gain]
        return channel, gain_id

    with pd.HDFStore(offsets_file) as st:
        for name in st.keys():
            channel, gain_id = name_to_channel_gain_id(name)
            df = st[name]
            df.sort_values(["cell","sample"], inplace=True)
            offsets[channel, gain_id] = df["median"].values.reshape(-1, 40)

    return offsets


class TimelapseCalibrationExtraOffsets:

    def __init__(self, fits_file, offsets_file):
        self.calib_constants = read_calib_constants(fits_file)
        self.offsets = read_offsets(offsets_file)
        self.roi = None
        self.sample = None

    def offset(self, delta_t, a, b):
        o = a * delta_t ** b
        o[np.isnan(o)] = 0
        return o

    def __call__(self, event):
        ''' calibrate data in event '''
        event = deepcopy(event)

        if self.roi is None:
            self.roi = event.roi
            self.sample = np.arange(event.roi)

        assert self.roi == event.roi

        for pixel in range(len(event.data)):
            for gain in event.data.dtype.names:
                gain_id = {'high':0, 'low':1}[gain]
                sc = event.header.stop_cells[pixel][gain]
                cells = sample2cell(self.sample, sc)

                dt = event.time_since_last_readout[pixel][gain]
                c = self.calib_constants.loc[pixel, gain].loc[cells]
                delta_t_offset = self.offset(dt, c['a'], c['b']).astype('>i2')
                extra_offset = self.offsets[pixel, gain_id, cells, self.sample].astype('>i2')
                event.data[pixel][gain] -= delta_t_offset + extra_offset

        return event
