# Science

Doppler lidars collect profiles of radial wind velocities in the atmospheric boundary layer. In order to inform the Doppler lidar where to scan in order to detect regions of interest, such as the wake of wind farms during high widn events, an adaptive sensing capability is needed. This plugin contains the code needed to create a custom scan for the Halo Photonics Doppler lidar and send it to the lidar when a certain condition is satisfied. The default configuration will use the VAD scan's radial velocities from the Doppler lidar to determine the wind velocity at 100 m via the Atmospheric Radiation Measurement facility's VAP code (Newsom et al. 2017) in the Atmospheric Community Toolkit. It is then configured to perform a sector scan that targets the wind farm south of Nantucket.

# Using the code

The input data are autocorrelation function files from the ARM dlacf.a1 dataset. While the algorithm will work on input
SNR data, the design from raw data is there in order to support deciding how to process and store the data from the raw
observations before they are stored on the ARM archive.
The path to these files must be specified in the app.py file.

# Arguments
--verbose: Display more information

--input [ARM datastream]: The ARM datastream to use as input

--model [json file]: The model file to use.

--interval [time interval]: The time interval to classify over

--date: The date to pull data from. Set to None to use latest date/time.

--time: The time to pull data from.

# Ontology

The algorithm will then output scene classifications (weather.classifier.class) 
over five minute time periods. 

weather.classifier.class: The three classifications supported are
currently 'clear', 'cloudy', and 'rainy'.

# Inferences from Sage Codes

To query the output classification from the plugin, simply do:

    import sage_data_client

    df = sage_data_client.query(start="-120m",
        filter={"name": "weather.classifier.class"}
    )
    print(df)

