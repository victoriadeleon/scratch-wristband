# improvements:
'''
uses buffers and locks to accumulate data before writing to CSV files,
reducing the file I/O operations

separate threads to writing data from buffers to files (in this way the main is focused on collecting data)

'''

import csv
import os
import random
import re
import socket
import threading
import time
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Initialize global variables
data_collection_accel = []
data_collection_cap = []

# this lists includes scratching and non-scratching activities
ACTIVITIES = [
    "scratch_lower_leg",
]  

current_activity = None
is_activity_running = False

acc_buffer = []
cap_buffer = []
buffer_size = 100

cap_times = []
acc_times = []
capacitance_vals = []
acc_vals = []

def find_latest_file_id(file_prefix, directory_path):
    max_id = None
    file_pattern = re.compile(f"^{file_prefix}_(\\d+)$")

    for file_name in os.listdir(directory_path):
        match = file_pattern.match(file_name.split(".")[0])
        if match:
            file_id = int(match.group(1))
            if max_id is None or file_id > max_id:
                max_id = file_id
    return max_id


# Directory to check (change this to the directory where your files are located)
directory_path = 'C:/Users/Lenovo/OneDrive - Instituto Tecnologico y de Estudios Superiores de Monterrey/RISS/Multimodal wristband project/Data collection_python/data/'

# Find the latest IDs for 'data_acc' and 'data_cap'
latest_data_acc_id = find_latest_file_id("data_acc", directory_path)
latest_data_cap_id = find_latest_file_id("data_cap", directory_path)

# Increment the ID for the next 'data_acc' file
if latest_data_acc_id is not None:
    latest_data_acc_id += 1

    latest_data_acc_id = 1

if latest_data_cap_id is not None:
    latest_data_cap_id += 1
else:
    latest_data_cap_id = 1

def seeed_esp32_thread():
    print("Creating server...")
    localIP     = "0.0.0.0"
    localPort   = 3030
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    s.bind((localIP, localPort))

    last_time = time.time()
    buffer = []
    last_num_acc = 0 
    last_num_cap = 0
    acc_data = []
    cap_data = []
    start_time = time.time()

    # Buffer to accumulate data
    acc_buffer = []
    cap_buffer = []
    buffer_size = 100  # Adjust the buffer size as needed

    # Lock for thread-safe operations
    buffer_lock = threading.Lock()

    def write_acc_data():
        global acc_buffer
        while True:
            time.sleep(1)  # Adjust the sleep time as needed
            with buffer_lock:
                if acc_buffer:
                    with open(directory_path + "data_acc_" + str(latest_data_acc_id) + ".csv", "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerows(acc_buffer)
                    acc_buffer = []

    def write_cap_data():
        global cap_buffer
        while True:
            time.sleep(1)  # Adjust the sleep time as needed
            with buffer_lock:
                if cap_buffer:
                    with open(directory_path + "data_cap_" + str(latest_data_cap_id) + ".csv", "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerows(cap_buffer)
                    cap_buffer = []

    # Start the writing threads
    threading.Thread(target=write_acc_data, daemon=True).start()
    threading.Thread(target=write_cap_data, daemon=True).start()

    try:
        while True:
            st = time.time()
            receivedData = s.recvfrom(4400) 
            buffer.extend(receivedData[0])

            while len(buffer) > 50:
                if (buffer[0] == 0 and buffer[1] == 255 and buffer[2] == 0 and buffer[3] == 255 and buffer[4] == 0):
                    # time is from buffer 6 to 9 but this needs to be converted properly
                    t = ((buffer[9] << 24)+ (buffer[8] << 16)+ (buffer[7] << 8)+ buffer[6])

                    # if accelerometer data
                    if buffer[5] == 1:
                        x = round(((buffer[13] << 24)+ (buffer[12] << 16)+ (buffer[11] << 8)+ buffer[10])/ 1000 - (4 * 9.81),4,)

                        if np.abs(x) > 9.81 * 4:
                            x = np.nan

                        y = round(((buffer[17] << 24)+ (buffer[16] << 16)+ (buffer[15] << 8)+ buffer[14])/ 1000- (4 * 9.81),4,)

                        if np.abs(y) > 9.81 * 4:
                            y = np.nan

                        z = round(((buffer[21] << 24)+ (buffer[20] << 16)+ (buffer[19] << 8)+ buffer[18])/ 1000- (4 * 9.81),4,)

                        if np.abs(z) > 9.81 * 4:
                            z = np.nan

                        with buffer_lock:
                            acc_buffer.append([t, current_activity, x, y, z])
                            if len(acc_buffer) >= buffer_size:
                                with open(directory_path + "data_acc_" + str(latest_data_acc_id) + ".csv", "a", newline="") as f:
                                    writer = csv.writer(f)
                                    writer.writerows(acc_buffer)
                                acc_buffer = []

                        acc_data.append([t, x, y, z])

                    # else if capacitance data
                    elif buffer[5] == 2:
                        vals = [t]
                        for i in range(0, 30):  # range is 30
                            v = (buffer[11 + 2 * i] << 8) + buffer[10 + 2 * i]
                            vals.append(v)
                        with buffer_lock:
                            cap_buffer.append([t, current_activity] + vals[1:])
                            if len(cap_buffer) >= buffer_size:
                                with open(directory_path + "data_cap_" + str(latest_data_cap_id) + ".csv", "a", newline="") as f:
                                    writer = csv.writer(f)
                                    writer.writerows(cap_buffer)
                                cap_buffer = []

                        cap_data.append(vals)
                buffer.pop(0)

                if time.time() - last_time > 1:
                    last_time = time.time()
                    print("Accelerometer Data collected in last second:", (len(acc_data) - last_num_acc))
                    print("Capactive Data collected in last second:", (len(cap_data) - last_num_cap))
                    last_num_acc = np.shape(acc_data)[0]
                    last_num_cap = np.shape(cap_data)[0]
    finally:
        s.close()

def countdown(duration):
    for i in range(duration, 0, -1):
        print(f"Time left: {i} seconds", end="\r")
        time.sleep(1)
    print("\nActivity ended.")


def perform_activity(activity_name, duration):
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

    with open(directory_path + "data_cap_" + str(latest_data_cap_id) + ".csv", "a", newline="") as f:
        writer = csv.writer(f)
        # adapt electrode number
        header = ["Timestamp", "Activity Name"] + [f"C{i}" for i in range(1, 31)]
        writer.writerow(header)

    # Wait for the user to start the sensor data reading thread
    input("Press Enter to start the sensor data collection thread...")
    threading.Thread(target=seeed_esp32_thread, daemon=True).start()

    time.sleep(5)  # Wait for the thread to start

    print("Created " + "data_" + "acc_" + str(latest_data_acc_id) + ".csv")
    print("Created " + "data_" + "cap_" + str(latest_data_cap_id) + ".csv")

    shuffled_activities = random.sample(ACTIVITIES, len(ACTIVITIES))  # Randomize activity order
    for activity_name in shuffled_activities:
        input(f"Press Enter to start {activity_name}:")
        is_activity_running = True  # Set the flag to indicate activity start
        perform_activity(activity_name, 8)  # Random duration between 3 and 8 seconds

    print("All activities completed and data saved.")

    # Graph plotting

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
