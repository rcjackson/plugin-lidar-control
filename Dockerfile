FROM waggle/plugin-base:1.1.1-base

RUN echo 4
RUN apt-get update -y
RUN apt-get install -y libhdf5-serial-dev
RUN apt-get install -y python3-h5py gcc python3-dev
RUN apt-get install -y python3-netcdf4
RUN apt-get install -y python3-h5netcdf
RUN pip3 install act-atmos
RUN pip3 install xarray
RUN pip3 install --upgrade pandas
RUN pip3 install paramiko
RUN pip3 install --upgrade pywaggle
RUN pip3 install sage_data_client
RUN pip3 install git+https://github.com/DAP-platform/dap-py.git

COPY . .
ENTRYPOINT ["python3", "send_scan_to_lidar_csm.py"]

