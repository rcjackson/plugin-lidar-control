import numpy as np
import act
import glob
import utils
import os
from send_scan_to_lidar import *

def convert_to_hours_minutes_seconds(decimal_hour, initial_time):
    delta = timedelta(hours=decimal_hour)
    return datetime(initial_time.year, initial_time.month, initial_time.day) + delta

def read_as_netcdf(file, lat, lon, alt):
    field_dict = utils.hpl2dict(file)
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


if len(sys.argv) > 1:
    file = sys.argv[1]
else:
    # Insert downloading code here

height_of_interest = 150.
threshold = 15.
lidar_ip = '10.crap'
lidar_user = os.environ['LIDAR_USER_NAME']
lidar_password = os.environ['LIDAR_PASSWORD']

dataset = read_as_netcdf(file, 41.98053299237866, -87.71662374616044, 0.)
dataset["signal_to_noise_ratio"] = dataset["intensity"] - 1
dataset = act.retrievals.compute_winds_from_ppi(dataset)
wind_at_height = ds["wind_speed"].sel(height=height_of_interest, method='nearest')
if wind_at_height >= threshold:
   send_scan(file, lidar_ip_addr, lidar_uname, lidar_pwd) 

