import numpy as np
import act
import glob
import utils
import os
import argparse
import pandas as pd
import xarray as xr

from datetime import datetime, timedelta

def convert_to_hours_minutes_seconds(decimal_hour, initial_time):
    delta = timedelta(hours=decimal_hour)
    return datetime(initial_time.year, initial_time.month, initial_time.day) + delta

def hpl2dict(file_path):
    #import hpl files into intercal storage
    with open(file_path, 'r') as text_file:
        lines=text_file.readlines()

    #write lines into Dictionary
    data_temp=dict()

    header_n=17 #length of header
    data_temp['filename']=lines[0].split()[-1]
    data_temp['system_id']=int(lines[1].split()[-1])
    data_temp['number_of_gates']=int(lines[2].split()[-1])
    data_temp['range_gate_length_m']=float(lines[3].split()[-1])
    data_temp['gate_length_pts']=int(lines[4].split()[-1])
    data_temp['pulses_per_ray']=int(lines[5].split()[-1])
    data_temp['number_of_waypoints_in_file']=int(lines[6].split()[-1])
    rays_n=(len(lines)-header_n)/(data_temp['number_of_gates']+1)

    '''
    number of lines does not match expected format if the number of range gates
    was changed in the measuring period of the data file (especially possible for stare data)
    '''
    if not rays_n.is_integer():
        print('Number of lines does not match expected format')
        return np.nan

    data_temp['no_of_rays_in_file']=int(rays_n)
    data_temp['scan_type']=' '.join(lines[7].split()[2:])
    data_temp['focus_range']=lines[8].split()[-1]
    data_temp['start_time']=pd.to_datetime(' '.join(lines[9].split()[-2:]))
    data_temp['resolution']=('%s %s' % (lines[10].split()[-1],'m s-1'))
    data_temp['range_gates']=np.arange(0,data_temp['number_of_gates'])
    data_temp['center_of_gates']=(data_temp['range_gates']+0.5)*data_temp['range_gate_length_m']

    #dimensions of data set
    gates_n=data_temp['number_of_gates']
    rays_n=data_temp['no_of_rays_in_file']

    # item of measurement variables are predefined as symetric numpy arrays filled with NaN values
    data_temp['radial_velocity'] = np.full([gates_n,rays_n],np.nan) #m s-1
    data_temp['intensity'] = np.full([gates_n,rays_n],np.nan) #SNR+1
    data_temp['beta'] = np.full([gates_n,rays_n],np.nan) #m-1 sr-1
    data_temp['spectral_width'] = np.full([gates_n,rays_n],np.nan)
    data_temp['elevation'] = np.full(rays_n,np.nan) #degrees
    data_temp['azimuth'] = np.full(rays_n,np.nan) #degrees
    data_temp['decimal_time'] = np.full(rays_n,np.nan) #hours
    data_temp['pitch'] = np.full(rays_n,np.nan) #degrees
    data_temp['roll'] = np.full(rays_n,np.nan) #degrees

    for ri in range(0,rays_n): #loop rays
        lines_temp = lines[header_n+(ri*gates_n)+ri+1:header_n+(ri*gates_n)+gates_n+ri+1]
        header_temp = np.asarray(lines[header_n+(ri*gates_n)+ri].split(),dtype=float)
        data_temp['decimal_time'][ri] = header_temp[0]
        data_temp['azimuth'][ri] = header_temp[1]
        data_temp['elevation'][ri] = header_temp[2]
        data_temp['pitch'][ri] = header_temp[3]
        data_temp['roll'][ri] = header_temp[4]
        for gi in range(0,gates_n): #loop range gates
            line_temp=np.asarray(lines_temp[gi].split(),dtype=float)
            data_temp['radial_velocity'][gi,ri] = line_temp[1]
            data_temp['intensity'][gi,ri] = line_temp[2]
            data_temp['beta'][gi,ri] = line_temp[3]
            if line_temp.size>4:
                data_temp['spectral_width'][gi,ri] = line_temp[4]

    return data_temp


def read_as_netcdf(file, lat, lon, alt):
    field_dict = hpl2dict(file)
    initial_time = pd.to_datetime(field_dict['start_time'])

    time = pd.to_datetime([convert_to_hours_minutes_seconds(x, initial_time) for x in field_dict['decimal_time']])

    ds = xr.Dataset(coords={'range':field_dict['center_of_gates'],
                            'time': time,
                            'azimuth': ('time', field_dict['azimuth']),
                            'elevation': ('time', field_dict['elevation'])} ,
                    data_vars={'radial_velocity':(['time', 'range'],
                                                  field_dict['radial_velocity'].T),
                               'beta': (('time', 'range'), 
                                        field_dict['beta'].T),
                               'intensity': (('time', 'range'),
                                             field_dict['intensity'].T),
                               'spectral_width': (('time', 'range'),
                                             field_dict['spectral_width'].T)
                              }
                   )
    # Fake field for PYDDA
    ds['reflectivity'] = -99 * xr.ones_like(ds['beta'])
    ds['azimuth'] = xr.where(ds['azimuth'] >= 360.0, ds['azimuth'] - 360.0, ds['azimuth'])
    diff_azimuth = ds['azimuth'].diff(dim='time').values
    diff_elevation = ds['elevation'].diff(dim='time').values
    unique_elevations = np.unique(ds["elevation"].values)
    if len(ds['time'].values) == 6:
        unique_elevations = np.array([60])
    counts = np.zeros_like(unique_elevations)
    
    for i in range(len(unique_elevations)):
        counts[i] = np.sum(ds["elevation"].values == unique_elevations[i])
    
    if np.sum(np.abs(diff_azimuth) > 0.02) <= 2  and not np.all(ds['elevation'] == 90.0):
        sweep_mode = 'rhi'
        n_sweeps = 1
    elif np.all(ds['elevation'] == 90.0):
        sweep_mode = 'vertical_pointing'
        n_sweeps = 1
    else:
        # We will filter out the transitions between sweeps
        diff_elevation = xr.DataArray(np.pad(np.abs(diff_elevation), (1, 0), constant_values=(0, 0)), dims='time')
        sweep_mode = "azimuth_surveillance"
        ds = ds.where(diff_elevation < 0.01)
    ds['sweep_mode'] = xr.DataArray(np.array([sweep_mode.lower()], dtype='S32'), dims=['string_length_32'])
    ds['azimuth'] = xr.where(ds['azimuth'] < 360., ds['azimuth'], ds['azimuth'] - 360.)
    
    if sweep_mode == 'rhi':
        ds['fixed_angle'] = ('sweep', np.unique(ds['azimuth'].data[np.argwhere(np.abs(diff_azimuth) < 0.01) + 1]))
    elif sweep_mode == "azimuth_surveillance" or sweep_mode == "vertical_pointing":
        ds['fixed_angle'] = ('sweep', np.unique(ds['elevation'].data))
        n_sweeps = len(np.unique(ds['elevation'].data))
    ds['sweep_number'] = ('sweep', np.arange(0, n_sweeps))
    ds['sweep_number'].attrs["long_name"] = "sweep_index_number_0_based"
    ds['sweep_number'].attrs["units"] = ""
    ds['sweep_number'].attrs["_FillValue"] = -9999
    ds["latitude"] = lat
    ds["latitude"].attrs["long_name"] = 'latitude'
    ds["latitude"].attrs["units"] = "degrees_north"
    ds["latitude"].attrs["_FillValue"] = -9999.
    ds["longitude"] = lon
    ds["longitude"].attrs["long_name"] = 'longitude'
    ds["longitude"].attrs["units"] = "degrees_east"
    ds["longitude"].attrs["_FillValue"] = -9999.
    ds["altitude"] = alt
    ds["altitude"].attrs["long_name"] = alt
    ds["altitude"].attrs["units"] = "meters"
    ds["altitude"].attrs["_FillValue"] = -9999.
    num_rays = ds.dims['time']
    diff_elevation = ds["elevation"].diff(dim='time').values
    transitions = np.argwhere(np.abs(diff_elevation) > 0.01)
    
    end_indicies = [0]
    last_ind = 0
    for i, t in enumerate(transitions):
        if t - last_ind < 2:
            print(t)
        else:
            end_indicies.append(t[0])
            last_ind = t
    end_indicies.append(num_rays - 1)
    end_indicies = np.array(end_indicies)
    
    ds.attrs["Conventions"] = "CF-1.7"
    return ds

