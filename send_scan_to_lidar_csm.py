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
import sage_data_client

from doe_dap_dl import DAP
from utils import read_as_netcdf
from waggle.plugin import Plugin
AZ_COUNTS_PER_ROT = 500000
EL_COUNTS_PER_ROT = 250000

def make_scan_file(elevations, azimuths,
                   out_file_name, azi_speed=1.,
                   el_speed=0.1,
                   wait=0, acceleration=30, repeat=7,
                   rays_per_point=2, dyn_csm=False):
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
    dyn_csm: bool
        Set to True to send CSM assuming Dynamic CSM mode
    """    
    speed_azi_encoded = int(azi_speed * (AZ_COUNTS_PER_ROT / 360.))
    speed_el_encoded = int(el_speed * (EL_COUNTS_PER_ROT / 360.))
    clockwise = True
    no_points = len(azimuths) * len(elevations)
    with open(out_file_name, 'w') as output:
        if dyn_csm is False:
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

def send_scan(file_name, lidar_ip_addr, lidar_uname, lidar_pwd, out_file_name='user.txt', dyn_csm=False):
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
    dyn_csm: bool
        Set to True to assume Dynamic CSM mode
    """

    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
        print("Connected to the Lidar!")
        with ssh.open_sftp() as sftp:
            if dyn_csm is False:
                print(f"Writing {out_file_name} on lidar.")
                sftp.put(file_name, "/C:/Lidar/System/Scan parameters/%s" % out_file_name)
            else:
                sftp.put(file_name, f"/C:/Users/End User/DynScan/{out_file_name}")


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
    out_file_name = 'user.txt'
    parser = argparse.ArgumentParser()
    parser.add_argument('--wmag', type=float, default=2, 
            help='Max wind [TKE] threshold for triggering [m/s]')
    parser.add_argument('--trigger_tke', action="store_true",
            help="Trigger based off of TKE instead of winds")
    parser.add_argument('--trigger_node_hub_height', type=str, default="",
            help="Trigger based off of latest hub height winds from node")
    parser.add_argument('--trigger_node_llj_height', type=str, default="",
            help="Trigger based off of latest LLJ winds from node")
    parser.add_argument('--shear_top', type=float, default=1000, 
            help='Top vertical level for wind max calculation [m]')
    parser.add_argument('--shear_bottom', type=float, default=200,
            help='Bottom vertical level for wind max calculation [m]')
    parser.add_argument('--repeat', type=float, default=2, 
            help='Scan interval [min]')
    parser.add_argument('--dir_max', type=float, default=270,
            help='Upper limit of wind direction [degrees]')
    parser.add_argument('--dir_min', type=float, default=90,
            help='Lower limit of wind direction [degrees]')
    parser.add_argument('--upwind_min', type=float, default=None,
            help="Point upwind if in this interval [min].")
    parser.add_argument('--upwind_max', type=float, default=None,
            help="Point upwind if in this interval [max].")
    parser.add_argument('--lidar_ip_addr', type=str, default='10.31.81.87',
            help='Lidar IP address')
    parser.add_argument('--lidar_uname', type=str, default='end user',
            help='Lidar username')
    parser.add_argument('--lidar_pwd', type=str, default='',
            help='Lidar password')
    parser.add_argument('--dyn_csm', action="store_true",
            help="Set if lidar is running in Dynamic CSM mode.")
    parser.add_argument('--default_stare', action="store_true",
            help="Set if default strategy should be Stare and not VAD.")
    parser.add_argument('--trigger_sonic', default='',
            help="Trigger from latest b1-level Sonic anemometer data at specified site (i.e. wfip3/caco.sonic.z02)")
    parser.add_argument('--a2e_uname', default='',
            help="Username for atmosphere 2 electrons.")
    parser.add_argument('--a2e_passwd', default='',
            help="Password for atmosphere 2 electrons.")
    parser.add_argument('--cone_width', default=60.,
            help="Cone width for stacked sector scans")
    parser.add_argument('--trigger_hsrhi', action="store_true",
            help="Trigger HSRHI in along wind direction")
    parser.add_argument('--trigger_rhi', action="store_true",
            help="Trigger RHI in along wind direction")
    parser.add_argument('--trigger_ppis', action="store_true",
            help="Trigger PPI in along wind direction")
    parser.add_argument('--min_angle', default=5, type=float, help="Minimum elevation angle")
    parser.add_argument('--step', default=5, type=float, help="Step between scans.")
    parser.add_argument('--max_angle', default=5, type=float, help="Maximum elevation angle")
    parser.add_argument('--width', default=60, type=float, help="Width of PPI cone.")
    parser.add_argument('--speed', default=2, type=float, help="Rotation speed in degrees per second.")
    parser.add_argument('--az_offset', default=0., type=float, help="Azimuthal offset for lidar.")
    args = parser.parse_args()
    if not args.trigger_rhi and not args.trigger_ppis and not args.trigger_hsrhi:
        raise(ValueError, "User must specify scan to trigger in options (--trigger_(hsrhi/rhi/ppi).")
    rays_per_point = 1.
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
    if args.trigger_node_hub_height == "" and args.trigger_sonic == "" and args.trigger_node_llj_height == "":
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
            dataset = act.retrievals.compute_winds_from_ppi(
                    dataset, intensity_name='intensity') 
            max_wind = dataset['wind_speed'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).max(dim='height')
            max_wind_dir = dataset['wind_speed'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).argmax(dim='height').values
            max_wind_dir = dataset['wind_direction'].mean(dim='time').sel(height=slice(shear_bottom, shear_top)).values[max_wind_dir]
            if args.upwind_min is not None and args.upwind_max is not None:
                if args.upwind_min > args.upwind_max:
                    if max_wind_dir > args.upwind_min or max_wind_dir < args.upwind_max:
                        max_wind_dir = max_wind_dir + 180
                        if max_wind_dir >= 360.:
                            max_wind_dir = max_wind_dir - 360.
                else:
                    if max_wind_dir > args.upwind_min and max_wind_dir < args.upwind_max:
                        max_wind_dir = max_wind_dir + 180
                        if max_wind_dir >= 360.:
                            max_wind_dir = max_wind_dir - 360.

            if args.trigger_tke is True:    
                ds["radial_velocity"] = ds["radial_velocity"].where(ds["intensity"] > 1.008)
                tke = 0.5*(ds["radial_velocity"].std(dim='time')**2)
                sin60 = np.sqrt(3) / 2
                max_wind = tke.sel(
                    range=slice(shear_bottom * sin60, shear_top * sin60)).max(dim='range') 
                print(max_wind)
            
            if np.abs(max_wind) > wind_threshold and max_wind_dir > dir_min and max_wind_dir < dir_max:
                azimuths = np.array([max_wind_dir]) + args.az_offset
                azimuths[azimuths >= 360] -= 360
                elevations = np.arange(0, 180., 2.)
                deg_per_sec = 2.
                make_scan_file(elevations, azimuths, out_file_name,
                    azi_speed=deg_per_sec, el_speed=1, repeat=repeat, dyn_csm=args.dyn_csm)
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('change_true.txt',  lidar_ip_addr, lidar_uname,
                           lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)

                print("Triggering RHI")
                print("Max wind = %f, %f" % (max_wind, max_wind_dir))
                plugin.publish("lidar.strategy",
                                    1,
                                    timestamp=time.time_ns())
            else:
                azimuths = np.array([0, 60, 120, 180, 240, 300]) + args.az_offset
                azimuths[azimuths >= 360] -= 360.
                elevations = [60]
                deg_per_sec = 60
                make_scan_file(elevations, azimuths, out_file_name, wait=1000,
                    azi_speed=deg_per_sec, el_speed=1, repeat=repeat, dyn_csm=args.dyn_csm)
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('change_true.txt',  lidar_ip_addr, lidar_uname,

                           lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)

                print("Max wind = %f, %f" % (max_wind, max_wind_dir))
                print("Sending VAD profile")
                plugin.publish("lidar.strategy",
                                0,
                                timestamp=time.time_ns())
            if args.trigger_tke is False:
                plugin.publish("lidar.max_wind_speed", float(max_wind.values), timestamp=time.time_ns())
            else:
                plugin.publish("lidar.max_tke", float(max_wind.values), timestamp=time.time_ns())
            plugin.publish("lidar.max_wind_dir", max_wind_dir, timestamp=time.time_ns())
    elif args.trigger_sonic != "":
        with Plugin() as plugin:
            a2e = DAP('a2e.energy.gov', confirm_downloads=False)
            a2e.setup_basic_auth(username=args.a2e_uname, password=args.a2e_passwd)
            hour_ago = (datetime.datetime.now() - datetime.timedelta(minutes=180)).strftime("%Y%m%d%H%M%S")
            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filter_arg = {
                "Dataset": f"{args.trigger_sonic}.b1",
                "date_time": {"between": [hour_ago, now]},
                }
            file_list = a2e.search(filter_arg, table='inventory')
            a2e.download_files(file_list, path=os.getcwd())
            nc_list = sorted(glob.glob('*.nc'))
            sonic_data = xr.open_dataset(nc_list[-1])
            wind_speed = sonic_data['wind_speed'].values[0]
            wind_direction = sonic_data['wind_direction'].values[0]
            sonic_data.close()
            print(f"30 min wind speed: {wind_speed} direction: {wind_direction}")
            if args.upwind_min is not None and args.upwind_max is not None:
                if args.upwind_min > args.upwind_max:
                    if wind_direction > args.upwind_min or wind_direction < args.upwind_max:
                        wind_direction = wind_direction + 180
                        if wind_direction >= 360.:
                            wind_direction = wind_direction - 360.
                else:
                    if wind_direction > args.upwind_min and wind_direction < args.upwind_max:
                        wind_direction = wind_direction + 180
                        if wind_direction >= 360.:
                            wind_direction = wind_direction - 360.

            if wind_direction > dir_min and wind_direction < dir_max and wind_speed > wind_threshold:
                elevations = [2, 3, 4, 5, 7, 9, 11, 13, 15]
                azimuths = [wind_direction-30, wind_direction+30]
                azimuths = np.array(azimuths) + args.az_offset
                azimuths[azimuths >= 360] -= 360
                deg_per_sec = 2
                make_scan_file(elevations, azimuths, out_file_name,
                    azi_speed=deg_per_sec, el_speed=1, repeat=repeat, dyn_csm=args.dyn_csm)
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('change_true.txt',  lidar_ip_addr, lidar_uname,
                        lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)

                deg_per_sec = 2.
                plugin.publish("lidar.strategy",
                                1,
                                timestamp=time.time_ns())
                print("Triggering scan")
            else:
                elevations = [60.]
                azimuths = [0, 359.]
                deg_per_sec = 60
                plugin.publish("lidar.strategy",
                              0,
                            timestamp=time.time_ns())
                make_scan_file(elevations, azimuths, out_file_name, wait=0,
                    azi_speed=deg_per_sec, el_speed=1, repeat=repeat, dyn_csm=args.dyn_csm)
                print("Sending Stare...")
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('change_true.txt',  lidar_ip_addr, lidar_uname,
                         lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)
            plugin.publish("lidar.max_wind_speed", float(wind_speed), timestamp=time.time_ns())
            plugin.publish("lidar.max_wind_direction", float(wind_direction), timestamp=time.time_ns())

    else:
        with Plugin() as plugin:
            if args.trigger_node_llj_height == "" and not args.trigger_node_hub_height == "":
                df = sage_data_client.query(
                    start="-15m",
                    filter={
                        "plugin": ".*windprofile:2024.12.5",
                        "vsn": args.trigger_node_hub_height
                 })
                dir_key = "lidar.hub_wind_dir"
                spd_key = "lidar.hub_wind_spd"
                print(args.trigger_node_hub_height) 
            elif not args.trigger_node_llj_height == "" and args.trigger_node_hub_height == "":
                df = sage_data_client.query(
                    start="-15m",
                    filter={
                        "plugin": ".*windprofile:2024.12.5",
                        "vsn": args.trigger_node_llj_height
                 })
                dir_key = "lidar.llj_nose_dir"
                spd_key = "lidar.llj_nose_spd"
            else:
                raise ValueError("Cannot specify both triggering from LLJ and hub height.")
            if df.empty:
                if args.dyn_csm:
                    send_scan('change_false.txt',  lidar_ip_addr, lidar_uname,
                           lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                print("No wind profile data available within last 15 minutes.")
                plugin.publish("lidar.strategy",
                                0,
                                timestamp=time.time_ns())
                sys.exit(0)
            print(df["name"])
            df_dir = df.where(df["name"] == dir_key)
            df_spd = df.where(df["name"] == spd_key)
            print(df_dir["value"].mean(), df_spd["value"].mean())
            wind_speed = df_spd["value"].mean()
            wind_direction = df_dir["value"].mean()
            if args.upwind_min is not None and args.upwind_max is not None:
                if args.upwind_min > args.upwind_max:
                    if wind_direction > args.upwind_min or wind_direction < args.upwind_max:
                        wind_direction = wind_direction + 180
                        if wind_direction >= 360.:
                            wind_direction = wind_direction - 360.
                else:
                    if wind_direction > args.upwind_min and wind_direction < args.upwind_max:
                        wind_direction = wind_direction + 180
                        if wind_direction >= 360.:
                            wind_direction = wind_direction - 360.

            if wind_direction > dir_min and wind_direction < dir_max and wind_speed > wind_threshold:
                if args.trigger_hsrhi:
                    elevations = [0., 180.]
                    azimuths = [wind_direction + args.az_offset]
                    if azimuths[0] >= 360:
                        azimuths[0] -= 360.
                    el_speed = args.speed
                    az_speed = 3
                elif args.trigger_rhi:
                    elevations = [args.min_angle, args.max_angle]
                    azimuths = [wind_direction + args.az_offset]
                    if azimuths[0] >= 360:
                        azimuths[0] -= 360.
                    el_speed = args.speed
                    az_speed = 3
                elif args.trigger_ppis:
                    el_speed = 3
                    az_speed = args.speed
                    elevations = np.arange(args.min_angle, args.max_angle, args.step)
                    azimuths = [wind_direction - args.cone_width/2,
                            wind_direction + args.cone_width/2]
                    azimuths = np.array(azimuths)
                    azimuths[azimuths >= 360] -= 360

                deg_per_sec = 2
                make_scan_file(elevations, azimuths, out_file_name,
                    azi_speed=az_speed, el_speed=el_speed, repeat=repeat, dyn_csm=args.dyn_csm)
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('true.txt',  lidar_ip_addr, lidar_uname,
                           lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)

                deg_per_sec = 2.
                plugin.publish("lidar.strategy",
                                1,
                                timestamp=time.time_ns())
                print("Triggering scan")
            else:
                if args.default_stare:
                    elevations = [90.]
                    azimuths = [0, 1.]
                    print("Stare sent")
                else:
                    elevations = [60.]
                    azimuths = [0., 60., 120., 180., 270., 360.]
                    azimuths = np.array(azimuths) + args.az_offset
                    azimuths[azimuths >= 360.] -= 360
                    print("VAD sent")
                deg_per_sec = 60
                plugin.publish("lidar.strategy",
                                0,
                                timestamp=time.time_ns())
                make_scan_file(elevations, azimuths, out_file_name, wait=1000,
                    azi_speed=deg_per_sec, el_speed=1, repeat=repeat, dyn_csm=args.dyn_csm)
                if args.dyn_csm:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        "scan.txt", dyn_csm=args.dyn_csm)
                    send_scan('change_true.txt',  lidar_ip_addr, lidar_uname,
                           lidar_pwd, out_file_name='change.txt', dyn_csm=args.dyn_csm)
                else:
                    send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd,
                        out_file_name, dyn_csm=args.dyn_csm)
            plugin.publish("lidar.max_wind_speed", float(wind_speed), timestamp=time.time_ns())
            plugin.publish("lidar.max_wind_direction", float(wind_direction), timestamp=time.time_ns())

        print("Uploading User files...")
        if cur_time.minute < 15:
            cur_time = cur_time - datetime.timedelta(hours=1)
            for f in file_list:
                if 'User' in f:            
                    time_string = '%d%02d%02d_%02d' % (cur_time.year, cur_time.month, cur_time.day, 
                            cur_time.hour)
                    if time_string in f:
                        print(f)
                        with Plugin() as plugin:
                            plugin.upload_file(f)          
