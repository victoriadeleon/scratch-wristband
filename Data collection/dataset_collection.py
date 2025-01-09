import csv # handles writing and reading csv files
import os # interacts with the operating system (directory/file management)
import random # to randomize activity order and durations
import re # handles regular expressions for string marching (like parsing file names)
import socket # for socket operations that allow communication with the wristband
import threading # for multi-threading operations (e.g. data collection while running activities)
import time # handles time operations (delays, timestamps)
import keyboard
import matplotlib.pyplot as plt # for plotting graphs
import numpy as np # for numerical operations
import pandas as pd # for data manipulation and analysis
import serial # for serial communication with the wristband
from serial.tools import list_ports # finds available serial ports

# Initialize global variables
data_collection_accel = []
data_collection_cap = []

# this lists includes scratching and non scratching activities
ACTIVITIES = [
    "scratch_lower_leg",
    "scratch_back",
    "scratch_arm",
]  

current_activity = None
is_activity_running = False

# to store timestamps for capacitance and accelerometer data
cap_times = []
acc_times = []

# to store capacitance and accelerometer values
capacitance_vals = []
acc_vals = []

###### FILE ID FINDER #######
def find_latest_file_id(file_prefix, directory_path):
    max_id = None # Tracks the highest ID found so far
    file_pattern = re.compile(f"^{file_prefix}_(\\d+)$")

    for file_name in os.listdir(directory_path): # Loop through all files in the directory
        match = file_pattern.match(file_name.split(".")[0]) # Check if the file name matches the pattern
        if match: # if a match is found, extract the ID and compare it with the current max ID
            file_id = int(match.group(1))
            if max_id is None or file_id > max_id:
                max_id = file_id
    return max_id # Return the highest ID found

# Directory path where the data files will be saved (write the direction to your 'data' folder)
directory_path = 'C:/Users/Lenovo/OneDrive - Instituto Tecnologico y de Estudios Superiores de Monterrey/RISS/Multimodal wristband project/Data collection_python/data/'

# Find the latest IDs for 'data_acc' and 'data_cap'
latest_data_acc_id = find_latest_file_id("data_acc", directory_path)
latest_data_cap_id = find_latest_file_id("data_cap", directory_path)

# Increment the ID for the next 'data_acc' file
if latest_data_acc_id is not None:
    latest_data_acc_id += 1
else:
    latest_data_acc_id = 1

if latest_data_cap_id is not None:
    latest_data_cap_id += 1
else:
    latest_data_cap_id = 1

###### DATA COLLECTION THREAD #######
def seeed_esp32_thread():
    print("Creating server...")
    localIP     = "0.0.0.0" # listens on all network interfaces
    localPort   = 3030 # port to listen on 
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM) # create a UDP socket object
    s.bind((localIP, localPort)) # bind the socket to the address and port

    last_time = time.time() # last time data was processed
    buffer = [] # temporary storage for incoming packets

    # tracks the number of accelerometer and capacitance data points collected
    last_num_acc = 0 
    last_num_cap = 0

    # local storage for accelerometer and capacitance data
    acc_data = [] 
    cap_data = [] 

    # start time of the data collection
    start_time = time.time()

    try:
        while True: # this loop runs indefinitely to receive and process data packets sent by the ESP32
            st = time.time() # timestamp initialization

            receivedData = s.recvfrom(4400)  # Receive a packet
            buffer.extend(receivedData[0]) # Append the packet to the buffer

            while len(buffer) > 50: # Process packets when the buffer is full. Note: 50 bytes is the minimum size of a valid data packet as per the protocol
                if (buffer[0] == 0 and buffer[1] == 255 and buffer[2] == 0 and buffer[3] == 255 and buffer[4] == 0): # Check for a valid header [0, 255, 0, 255, 0]
                    # Combines bytes 6 to 9 using bitwise shifts to reconstruct a 32-bit timestamp
                    t = ((buffer[9] << 24)+ (buffer[8] << 16)+ (buffer[7] << 8)+ buffer[6])

                    # if accelerometer data, extract x,y,z values
                    # divides by 1000 to scale and subtracts 4g to get the acceleration in m/s^2
                    if buffer[5] == 1:
                        x = round(((buffer[13] << 24)+ (buffer[12] << 16)+ (buffer[11] << 8)+ buffer[10])/ 1000 - (4 * 9.81),4,)

                        # To handle invalid data, it sets x to nan if it goes beyond the range of -4g to 4g.
                        # Most human activities, recorded by a wearable device, are unlikely to exceed this range. 
                        # Values beyond this range are likely due to noise or other issues like device malfunction.
                        if np.abs(x) > 9.81 * 4: 
                            x = np.nan
                        y = round(((buffer[17] << 24)+ (buffer[16] << 16)+ (buffer[15] << 8)+ buffer[14])/ 1000- (4 * 9.81),4,)

                        if np.abs(y) > 9.81 * 4:
                            y = np.nan
                        z = round(((buffer[21] << 24)+ (buffer[20] << 16)+ (buffer[19] << 8)+ buffer[18])/ 1000- (4 * 9.81),4,)

                        if np.abs(z) > 9.81 * 4:
                            z = np.nan
                        # save accelerometer data to a csv file. Writes the timestamp, activity name, x, y, z values
                        with open(directory_path + "data_acc_"+ str(latest_data_acc_id) + ".csv", "a", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([t, current_activity, x, y, z])

                        acc_data.append([t, x, y, z])

                    # else if capacitance data
                    elif buffer[5] == 2:
                        # extract capacitance values.
                        vals = [t]
                        for i in range(0, 30):  # range is 30
                            v = (buffer[11 + 2 * i] << 8) + buffer[10 + 2 * i]
                            vals.append(v)

                        # save capacitance data to a csv file. Writes the timestamp, activity name, and capacitance values
                        with open(directory_path + "data_cap_" + str(latest_data_cap_id) + ".csv", "a", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([t, current_activity] + vals[1:])  # Adjusted to include all values from vals
                        cap_data.append(vals)
                buffer.pop(0)

                if time.time() - last_time > 1: # checks if one second has passed since the last udpate
                    last_time = time.time()
                    # get the last acc_data and cap_data

                    print("Acc_data:", acc_data[-1])
                    print("Cap_data:", cap_data[-1])
                    #print(np.shape(acc_data))
                    #print(np.shape(cap_data))

                    # Calculates and prints the number of accelerometer and capacitance packets processed in the last second.
                    # USE THESE LINES TO VERIFY THAT YOUR CODE IS WORKING PROPERLY

                    print("Accelerometer Data collected in last second:", (len(acc_data) - last_num_acc))
                    print("Capactive Data collected in last second:", (len(cap_data) - last_num_cap))

                    #print(np.shape(cap_data))
                    #print("Cap sampling freq:", len(cap_data) - last_num_cap)

                    # update counters for the total number of packets processed
                    last_num_acc = np.shape(acc_data)[0]
                    last_num_cap = np.shape(cap_data)[0]
    finally:
        s.close() # close the socket when the loop ends

def countdown(duration): # countdown function to display the time left for each activity
    for i in range(duration, 0, -1):
        print(f"Time left: {i} seconds", end="\r")
        time.sleep(1)
    print("\nActivity ended.")

def perform_activity(activity_name, duration): # Executes an activity for a given duration using the countdown function in a separate thread
    global current_activity, is_activity_running
    current_activity = activity_name
    is_activity_running = True
    print(f"Performing: {activity_name} for {duration} seconds")
    countdown_thread = threading.Thread(target=countdown, args=(duration,))
    countdown_thread.start()
    countdown_thread.join()  # Wait for the countdown to finish
    is_activity_running = False
    current_activity = None  # Reset current activity

def main():
    # opening the csv files to write the data
    # accelerometer data
    with open(directory_path + "data_acc_"+ str(latest_data_acc_id) + ".csv", "a", newline="") as f:

        writer = csv.writer(f)
        writer.writerow(
            [
                "Timestamp",
                "Activity Name",
                "X",
                "Y",
                "Z",
            ]
        )
   # capacitance data
    with open(directory_path + "data_cap_" + str(latest_data_cap_id) + ".csv", "a", newline="") as f:
        writer = csv.writer(f)
        # important note: adapt electrode number so it corresponds to the wristband
        header = ["Timestamp", "Activity Name"] + [f"C{i}" for i in range(1, 31)]
        writer.writerow(header)

    # Wait for the user to start the sensor data reading thread
    input("Press Enter to start the sensor data collection thread...")
    threading.Thread(target=seeed_esp32_thread, daemon=True).start()

    time.sleep(5)  # Wait for the thread to start

    print("Created " + "data_" + "acc_" + str(latest_data_acc_id) + ".csv")
    print("Created " + "data_" + "cap_" + str(latest_data_cap_id) + ".csv")

    shuffled_activities = random.sample(ACTIVITIES, len(ACTIVITIES))  # Randomize the order of activities
    for activity_name in shuffled_activities:
        input(f"Press Enter to start {activity_name}:")
        is_activity_running = True  # Set the flag to indicate activity start
        perform_activity(activity_name, np.random.randint(3, 6))  # Random duration between 3 and 5 seconds

    print("All activities completed and data saved.")

    ##### DATA PLOTTING #####

    # Define file paths
    acc_file_path = (directory_path + "data_acc_"+ str(latest_data_acc_id) + ".csv").format(latest_data_acc_id)
    cap_file_path = (directory_path + "data_cap_"+ str(latest_data_cap_id) + ".csv").format(latest_data_cap_id)

    # Load data from CSV files
    def load_data(file_path):
        return pd.read_csv(file_path)

    # Load accelerometer and capacitance data
    acc_data = load_data(acc_file_path)
    cap_data = load_data(cap_file_path)

    # Remove Duplicate Rows
    acc_data = acc_data.drop_duplicates()
    cap_data = cap_data.drop_duplicates()

    # Remove NaN values
    acc_data = acc_data.dropna()
    cap_data = cap_data.dropna()

    # Create a figure and a set of subplots
    fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(16, 6))

    # Plotting accelerometer data on the first subplot
    axs[0].plot(acc_data["Timestamp"], acc_data["X"], label="X-axis")
    axs[0].plot(acc_data["Timestamp"], acc_data["Y"], label="Y-axis")
    axs[0].plot(acc_data["Timestamp"], acc_data["Z"], label="Z-axis")
    axs[0].set_title("Accelerometer Data (X, Y, Z)")
    axs[0].set_xlabel("Timestamp")
    axs[0].set_ylabel("Acceleration (m/s²)")
    axs[0].legend()

    # Plotting capacitance data on the second subplot
    for i in np.arange(0, 30):
        axs[1].plot(
            cap_data["Timestamp"],
            cap_data["C" + str(i+1)],
            label=str(i+1),
        )
    axs[1].set_title("Capacitance Data")
    axs[1].set_xlabel("Timestamp")
    axs[1].set_ylabel("Capacitance")
    axs[1].legend()

    plt.tight_layout()
    plt.show()

### Note: script to open csv files and plot everything out.
if __name__ == "__main__":
    main()
