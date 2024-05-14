## Halo Photonics Doppler lidar triggering

This plugin will trigger a given scan strategy when a connected Halo Photonics Doppler lidar is properly configured. SFTP must be enabled on the connected lidar for this to work. In addition, the scan strategy must be set to collect VADs every fixed time interval to calculate the wind shear for the triggering. Finally, the User1 scan must be enabled in the Scan Scheduler.

This plugin, given arrays of azimuths describing a PPI scan, or elevations for RHIs, will send a CSM-format scan strategy to user.txt in the destination Doppler lidar. It will choose to send your scan if the wind shear retrieved from the VAD scan is above specified wind magnitude and direction thresholds. 

## Arguments
    
    --smag: Vertical wind shear magnitude threshold for triggering [2 m s between heights default]
    --sdir: Vertical wind shear direction threshold for triggering [90 degrees default]
    --shear_top: Top hegith for calculating vertical wind shear (default = 1000 m)
    --shear_bottom: Bottom height for calculating vertical wind shear (default = 200 m)
    --repeat: Repeat scan every x minutes
    --lidar_ip_addr: Lidar's IP address
    --lidar_uname: Lidar's username
    --lidar_pwd: Lidar's password


# Data Query
To query the last hour of data, do:
```
df = sage_data_client.query(
            start="-1h",
            filter={"name": "upload", "vsn": "W08D",
                   "plugin": "10.31.81.1:5000/local/plugin-lidarcontrol"},).set_index("timestamp")
```                   
The names of the available files are in the *value* key of the dataframe.
