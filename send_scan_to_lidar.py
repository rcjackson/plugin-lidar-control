import paramiko
import numpy as np

def make_scan_file(repeat, rays_per_point, 
                   elevations, azimuths, out_file_name,
                   beam_width=1):
    """
    Makes a scanning strategy file for a Halo Photonics Doppler Lidar.
    
    Parameters
    ----------
    repeat: int
        Number of times to repeat
    no_points: int
        The number of points to collect in the ray
    rays_per_point: float
        The number of rays per point
    no_sweeps: int
        The number of sweeps in the strategy
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
    # PPI scan
    if isinstance(azimuths, tuple):
        min_azi = azimuths[0]
        max_azi = azimuths[1]

        if max_azi < min_azi:
            no_points = int((max_azi + 360.0 - min_azi)/beam_width)
        else:
            no_points = int((max_azi - min_azi)/beam_width)
        no_sweeps = len(elevations)
        no_points = no_points * no_sweeps
        with open(out_file_name, 'w') as fi:
            fi.write('%d\r\n' % repeat)
            fi.write('%d\r\n' % no_points)
            fi.write('%d\r\n' % rays_per_point)
            for i in range(no_sweeps):
                cur_azi = min_azi
                while(not np.abs(cur_azi - max_azi) < beam_width):
                    cur_azi = cur_azi + beam_width
                    if cur_azi > 360.0:
                        cur_azi = cur_azi - 360.0
                    string = "%07.3f%07.3f\r\n" % (cur_azi, elevations[i])
                    fi.write(string) 

    if isinstance(elevations, tuple):
        min_el = elevations[0]
        max_el = elevations[1]

        if max_el < min_el:
            no_points = int((max_el + 360.0 - min_el)/beam_width)
        else:
            no_points = int((max_el - min_el)/beam_width)
        
        with open(out_file_name, 'w') as fi:
            fi.write('%d\r\n' % repeat)
            fi.write('%d\r\n' % no_points)
            fi.write('%d\r\n' % rays_per_point)
            
            cur_el = min_el
            while(not np.abs(cur_el - max_el) < beam_width):
                cur_el = cur_el + beam_width
                if cur_el > 180.0:
                    cur_el = cur_el - 180.0
                string = "%07.3f%07.3f\r\n" % (azimuths, cur_el)
                fi.write(string) 

out_file_name = 'user.txt'
lidar_ip_addr = '192.168.1.90'
lidar_uname = 'waggle'
lidar_pwd = 'w8ggl3'

rays_per_point = 1.
azimuths = 60.
elevations = (0., 90.)
make_scan_file(7., rays_per_point, elevations, azimuths, out_file_name)

with paramiko.SSHClient() as ssh:
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
    print("Connected to the Lidar!")
    with ssh.open_sftp() as sftp:
        sftp.put(out_file_name, "/C:/Lidar/System/Scan parameters/%s" % out_file_name)
        print("New scan strategy available as %s on Lidar" % out_file_name)

