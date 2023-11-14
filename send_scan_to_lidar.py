import paramiko
import numpy as np

def make_scan_file(azimuths, elevations, out_file_name):
    """
    Makes a scanning strategy file for a Halo Photonics Doppler Lidar.
    
    Parameters
    ----------
    azimuths: float 1d array
        The azimuth of each ray.
    elevations: float 1d array
        The elevation of each ray in the scan.
    out_file_name: str
        The output name of the file.
    """    
    if not len(azimuths) == len(elevations):
        raise ValueError("Azimuths and elevations must have same shape!")
    
    with open(out_file_name, 'w') as fi:
        for i in range(len(azimuths)):
            string = "%07.3f%07.3f\n" % (azimuths[i], elevations[i])
            print(string)
            fi.write(string) 

out_file_name = 'user4.txt'
lidar_ip_addr = '192.168.1.90'
lidar_uname = 'waggle'
lidar_pwd = 'w8ggl3'

azimuths = np.arange(0, 60., 1.)
elevations = 4 * np.ones_like(azimuths)
make_scan_file(azimuths, elevations, out_file_name)

with paramiko.SSHClient() as ssh:
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(lidar_ip_addr, username=lidar_uname, password=lidar_pwd)
    print("Connected to the Lidar!")
    with ssh.open_sftp() as sftp:
        sftp.put(out_file_name, "/C:/Lidar/System/Scan parameters/%s" % out_file_name)
        print("New scan strategy available as %s on Lidar" % out_file_name)

