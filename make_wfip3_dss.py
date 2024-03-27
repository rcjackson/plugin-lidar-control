from datetime import datetime, timedelta

start_time = datetime(2020, 3, 14, 0, 0, 0)
# Make the Daily Scan Schedule text file for WFIP3
with open('scan.dss', 'w') as dss_file:
    while start_time < datetime(2020, 3, 15, 0, 0):
        if start_time.minute < 10:
            dss_file.write("%s\tprofile\t1\tS\t0\r\n" % start_time.strftime('%H%M%S'))
        start_time = start_time + timedelta(seconds=5)
