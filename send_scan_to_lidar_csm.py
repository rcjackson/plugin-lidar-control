import numpy as np
import paramiko

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
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
        print("Connected to the Lidar!")
        with ssh.open_sftp() as sftp:
            sftp.put(file_name, "/C:/Lidar/System/Scan parameters/%s" % out_file_name)
            print("New scan strategy available as %s on Lidar" % out_file_name)

out_file_name = 'ppi0.5.txt'
lidar_ip_addr = '10.31.81.87'
lidar_uname = 'end user'
lidar_pwd = 'mju7^TFC'

rays_per_point = 1.
azimuths = np.arange(0., 360., 1)
elevations = [0.1]

make_scan_file(elevations, azimuths, out_file_name, azi_speed=1, el_speed=0.005)
send_scan(out_file_name, lidar_ip_addr, lidar_uname, lidar_pwd)    
