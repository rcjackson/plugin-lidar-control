import numpy as np
import paramiko
import act
import argparse
import glob
import sys
import datetime
import time
import os
import xarray as xr

from utils import read_as_netcdf
from waggle.plugin import Plugin
AZ_COUNTS_PER_ROT = 500000
EL_COUNTS_PER_ROT = 250000

def make_scan_file(elevations, azimuths,
                   out_file_name, azi_speed=1.,
                   el_speed=0.1,
                   wait=0, acceleration=30, repeat=7,
                   rays_per_point=2):
    """
    Makes a scanning strategy file for a Halo Photonics Doppler Lidar.
    
    Parameters
    ----------
    no_points: int
        The number of points to collect in the ray
    elevations: float 1d array or tuple
        The elevation of each sweep in the scan. If this is a 2-tuple, then
        the script will generate an RHI spanning the smallest to largest elevation
    azimuths: float or 2-tuple
        If this is a 2-tuple, then this script will generate a PPI from min_azi to max_azi.
    out_file_name: str
        The output name of the file.
    beam_width: float
        The spacing between beams.
    
    """    
    speed_azi_encoded = int(azi_speed * (AZ_COUNTS_PER_ROT / 360.))
    speed_el_encoded = int(el_speed * (EL_COUNTS_PER_ROT / 360.))
    clockwise = True
    no_points = len(azimuths) * len(elevations)
    with open(out_file_name, 'w') as output:
        output.write('%d\r\n' % repeat)
        output.write('%d\r\n' % no_points)
        output.write('%d\r\n' % rays_per_point)
  
        for el in elevations:
            if clockwise:
                az_array = azimuths
            else:
                az_array = azimuths.reverse()
            for az in az_array:
                azi_encoded = -int(az * (AZ_COUNTS_PER_ROT / 360.))
                el_encoded = -int(el * (EL_COUNTS_PER_ROT / 360.))
                output.write("A.1=%d,S.1=%d,P.1=%d*A.2=%d,S.2=%d,P.2=%d\r\n" %
                             (acceleration, speed_azi_encoded, azi_encoded,
                              acceleration, speed_el_encoded, el_encoded))
                output.write('W%d\r\n' % (wait))
            clockwise = ~clockwise
    return

def send_scan(file_name, lidar_ip_addr, lidar_uname, lidar_pwd, out_file_name='user.txt'):
    """

    Sends a scan to the lidar

    Parameters
    ---------
    file_name: str
        Path to the CSM-format scan strategy
    lidar_ip_addr:
        IP address of the lidar
    lidar_uname:
        The username of the lidar
    lidar_password:
        The lidar's password
    out_file_name:
        The output file name on the lidar
    """

    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
        print("Connected to the Lidar!")
        with ssh.open_sftp() as sftp:
            sftp.put(file_name, "/C:/Lidar/System/Scan parameters/%s" % out_file_name)
            print("New scan strategy available as %s on Lidar" % out_file_name)

def get_file(time, lidar_ip_addr, lidar_uname, lidar_pwd):
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("Connecting to %s" % lidar_ip_addr)
        ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
        print("Connected to the Lidar!")
        year = time.year
        day = time.day
        month = time.month
        hour = time.hour
        prev_hour = time - datetime.timedelta(hours=1)
        file_path = "/C:/Lidar/Data/Proc/%d/%d%02d/%d%02d%02d/" % (year, year, month, year, month, day)
        print(file_path)
        with ssh.open_sftp() as sftp:
            file_list = sftp.listdir(file_path)
            time_string = '%d%02d%02d_%02d' % (year, month, day, hour)
            time_string_prev = '%d%02d%02d_%02d' % (prev_hour.year, prev_hour.month, prev_hour.day, prev_hour.hour)
            file_name = None
           
            for f in file_list:
                if time_string in f or time_string_prev in f: 
                    file_name = f
                    base, name = os.path.split(file_name)
                    print(print(file_name))
                    sftp.get(os.path.join(file_path, file_name), name)
            if file_name is None:
                print("%s not found!" % str(time))
                return


if __name__ == "__main__":
    out_file_name = 'user1.txt'

    parser = argparse.ArgumentParser()
    parser.add_argument('--wmag', type=float, default=2, 
            help='Max wind [TKE] threshold for triggering [m/s]')
    parser.add_argument('--trigger_tke',action="store_true",
            help="Trigger based off of TKE instead of winds")
    parser.add_argument('--shear_top', type=float, default=1000, 
            help='Top vertical level for wind max calculation [m]')
    parser.add_argument('--shear_bottom', type=float, default=200,
            help='Bottom vertical level for wind max calculation [m]')
    parser.add_argument('--repeat', type=float, default=2, 
            help='Scan interval [min]')
    parser.add_argument('--dir_max', type=float, default=270,
            help='Upper limit of wind direction [degrees]')
    parser.add_argument('--dir_min', type=float, default=90,
            help='Lower limit of wind directionn [degrees]')
    parser.add_argument('--lidar_ip_addr', type=str, default='10.31.81.87',
            help='Lidar IP address')
    parser.add_argument('--lidar_uname', type=str, default='end user',
            help='Lidar username')
    parser.add_argument('--lidar_pwd', type=str, default='',
            help='Lidar password')
    rays_per_point = 1.
    args = parser.parse_args()
    wind_threshold = args.wmag
    shear_top = args.shear_top
    shear_bottom = args.shear_bottom
    lidar_ip_addr = args.lidar_ip_addr
    lidar_uname = args.lidar_uname
    lidar_pwd = args.lidar_pwd
    repeat = args.repeat
    dir_min = args.dir_min
    dir_max = args.dir_max
    # Get the latest VAD
    nant_lat_lon = (41.28079475342454, -70.16484695039435)
    cur_time = datetime.datetime.now()
    get_file(cur_time, lidar_ip_addr, lidar_uname, lidar_pwd)
    file_list = glob.glob('*.hpl')
    print(file_list) 
    dataset = None
    ds_list = []
    file_list = sorted(file_list)[-1:0:-1]
    need_update = False
    for f in file_list:
        if 'User2' in f:
            dataset = read_as_netcdf(f, nant_lat_lon[0], nant_lat_lon[1], 0)
            if np.all(dataset["elevation"] < 60) or dataset.sizes["time"] < 20:
                dataset = None
                continue
            dataset = dataset.where(dataset.elevation < 89., drop=True)
            dataset = dataset.drop_dims("sweep")
            # Last dataset is a stacked PPI, let's send a VAD
            print("Processing VAD from %s" % f)
            if args.trigger_tke is False:
                ds_list = [dataset]
                break
            else:
                ds_list.append(dataset)
                break
    ds = xr.concat(ds_list, dim='time')
    print("Loaded dataset")
    if ds is not None:
        ds.to_netcdf('test.nc')
        dataset = xr.open_dataset('test.nc')
    with Plugin() as plugin:    
        if ds is None:
            print("Not triggering PPI")
            plugin.publish("lidar.strategy", 0,
                             timestamp=time.time_ns())
            azimuths = [max_wind_dir-25, max_wind_dir+25]
            sys.exit(0)
        
        dataset["signal_to_noise_ratio"] = dataset["intensity"] - 1
        print("Processing VAD")
        print(dataset)
        dataset = act.retrievals.compute_winds_from_ppi(dataset, intensity_name='intensity') 
        print(dataset['wind_speed']) 
        max_wind = dataset['wind_speed'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).max(dim='height')
        max_wind_dir = dataset['wind_speed'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).argmax(dim='height').values
        print(dataset['wind_speed'].sel(height=slice(shear_bottom, shear_top)))
        print(max_wind_dir)
        max_wind_dir = dataset['wind_direction'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).values[max_wind_dir]
        if args.trigger_tke is True:    
            ds["radial_velocity"] = ds["radial_velocity"].where(ds["intensity"] > 1.008)
            tke = 0.5*(ds["radial_velocity"].std(dim='time')**2)
            sin60 = np.sqrt(3) / 2
            max_wind = tke.sel(
                range=slice(shear_bottom * sin60, shear_top * sin60)).max(dim='range') 
            print(max_wind)
        if np.abs(max_wind) > wind_threshold and max_wind_dir > dir_min and max_wind_dir < dir_max:
            azimuths = [max_wind_dir-30, max_wind_dir+30]
            elevations = [2, 3, 4, 5, 7, 9, 11, 13, 15, 17]
            deg_per_sec = 2.
            print("Triggering PPI")
            print("Max wind = %f, %f" % (max_wind, max_wind_dir))
            plugin.publish("lidar.strategy",
                                    1,
                                    timestamp=time.time_ns())
        else:
            azimuths = [0, 10]
            elevations = [30]
            deg_per_sec = 30

            print("Max wind = %f, %f" % (max_wind, max_wind_dir))
            print("Not triggering PPI")
            plugin.publish("lidar.strategy",
                                0,
                                timestamp=time.time_ns())
        if args.trigger_tke is False:
            plugin.publish("lidar.max_wind_speed", float(max_wind.values), timestamp=time.time_ns())
        else:
            plugin.publish("lidar.max_tke", float(max_wind.values), timestamp=time.time_ns())
        plugin.publish("lidar.max_wind_dir", max_wind_dir, timestamp=time.time_ns())
        make_scan_file(elevations, azimuths, out_file_name,
                azi_speed=deg_per_sec, el_speed=1, repeat=repeat)
        send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd)    

        print("Uploading User1 files...")
        if cur_time.minute < 15:
            cur_time = cur_time - datetime.timedelta(hours=1)
            for f in file_list:
                if 'User' in f:            
                    time_string = '%d%02d%02d_%02d' % (cur_time.year, cur_time.month, cur_time.day, 
                            cur_time.hour)
                    if time_string in f:
                        print(f)
                        plugin.upload_file(f)          
