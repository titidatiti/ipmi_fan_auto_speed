#!/usr/bin/env python3

import curses
import subprocess
import re
import logging
import os
import time
from flask import Flask, jsonify
import threading

# Setup logging
logging.basicConfig(
    filename="/app/log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Spinner states for visual feedback
spinner_states = ["|", "/", "-", "\\"]

# Flask app setup
app = Flask(__name__)

# Global variable to store sensor data
sensor_data = {
    "highest_sensor_temp": None,
    "mean_fan_speed": None,
    "gpu_temp": None,
    "status": "waiting_for_sensors",
}

# switch for curses
use_curses = (
    False  # If you are not using the code in docker, you can enable curses for be
)


# Function to load IPMI configuration from environment variables
def load_ipmi_config():
    ipmi_ip = os.getenv("IPMI_IP", "127.0.0.1")  # Default if not found
    ipmi_user = os.getenv("IPMI_USER", "admin")  # Default if not found
    ipmi_pass = os.getenv("IPMI_PASS", "admin")  # Default if not found
    return ipmi_ip, ipmi_user, ipmi_pass


# Load the IPMI config from environment variables
IPMI_IP, IPMI_USER, IPMI_PASS = load_ipmi_config()


# Function to get the color for a value based on type and thresholds
def get_color_for_value(value, scale_type):
    if value is None:
        return 3  # Default to Red if value is None
    if scale_type == "temperature":
        if 34 <= value <= 38:
            return 1  # Green
        elif 38 < value <= 50:
            return 2  # Yellow
        elif 50 < value <= 70:
            return 4  # Orange
        else:
            return 3  # Red
    elif scale_type == "fan_speed":
        if 2000 <= value <= 5000:
            return 1  # Green
        elif 5000 < value <= 9000:
            return 2  # Yellow
        elif 9000 < value <= 13000:
            return 4  # Orange
        else:
            return 3  # Red


# Function to get fan information from remote IPMI
def get_fan_info():
    result = subprocess.run(
        [
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            IPMI_IP,
            "-U",
            IPMI_USER,
            "-P",
            IPMI_PASS,
            "sdr",
            "type",
            "fan",
        ],
        capture_output=True,
        text=True,
    )
    """
    if use_curses:
        logging.info(f"Get fan info: {result}")
    else:
        print(f"Get fan info: {result}")
    """
    return result.stdout.strip()


# Function to get temperature information from remote IPMI
def get_temp_info():
    result = subprocess.run(
        [
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            IPMI_IP,
            "-U",
            IPMI_USER,
            "-P",
            IPMI_PASS,
            "sdr",
            "type",
            "temperature",
        ],
        capture_output=True,
        text=True,
    )
    """
    if use_curses:
        logging.info(f"Get temp info: {result}")
    else:
        print(f"Get temp info: {result}")
    """
    return result.stdout.strip()


# Function to get GPU temperature information (if available)
def get_gpu_temp_info():
    result = subprocess.run(
        ["nvidia-smi", "-q", "-d", "TEMPERATURE"], capture_output=True, text=True
    )
    temp_info = result.stdout
    match = re.search(r"GPU Current Temp\s+:\s+(\d+) C", temp_info)
    return int(match.group(1)) if match else None


# Function to extract numeric values from strings based on a regex pattern
def extract_numeric_value(s, pattern):
    match = re.search(pattern, s)
    return float(match.group(1)) if match else None


# Function to set fan speed on remote IPMI
def set_fan_speed(speed):
    subprocess.run(
        [
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            IPMI_IP,
            "-U",
            IPMI_USER,
            "-P",
            IPMI_PASS,
            "raw",
            "0x30",
            "0x30",
            "0x02",
            "0xff",
            f"{speed:02x}",
        ]
    )


# Main function to handle the curses UI and logic
def main(stdscr):
    spinner_idx = 0
    cpu_count = 0  # To track the number of CPUs

    # Initialize curses colors if use_curses is True
    if use_curses:
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_RED)

        stdscr.timeout(1000)

    while True:
        if use_curses:
            stdscr.clear()

        # Get fan and temperature information
        fan_info = get_fan_info().split("\n")
        temp_info = get_temp_info().split("\n")

        # Correct temperature information labels
        corrected_temp_info = []
        for line in temp_info:
            if "Inlet Temp" in line:
                line = line.replace("Inlet Temp", "Board Inlet Temp")
            elif "Exhaust Temp" in line:
                line = line.replace("Exhaust Temp", "Board Exhaust Temp")
            elif "Temp" in line:
                cpu_count += 1
                line = line.replace("Temp", f"CPU_{cpu_count} Temp")

            corrected_temp_info.append(line)

        # Reset the CPU count for the next iteration
        cpu_count = 0

        # Extract highest temperature and mean fan speed
        highest_sensor_temp = max(
            [
                extract_numeric_value(s, r"\b(\d+\.?\d*) degrees C\b")
                for s in temp_info
                if extract_numeric_value(s, r"\b(\d+\.?\d*) degrees C\b") is not None
            ]
        )
        fan_speeds = [
            extract_numeric_value(s, r"\b(\d+\.?\d*) RPM\b")
            for s in fan_info
            if extract_numeric_value(s, r"\b(\d+\.?\d*) RPM\b") is not None
        ]
        mean_fan_speed = int(sum(fan_speeds) / len(fan_speeds)) if fan_speeds else 0
        gpu_temp = get_gpu_temp_info()

        # Sometimes when the server just boot, cannot get the temperature and the container will exit. Wait until the temperature is valid.
        tempValid = True
        if highest_sensor_temp is None:
            tempValid = False
            print("Sensors are not ready yet, wait for 5 seconds...")

        if gpu_temp is None:
            tempValid = False
            print("nvidia-smi is not ready yet, wait for 5 seconds...")

        if not tempValid:
            time.sleep(5)
            continue

        max_temp = max(highest_sensor_temp, gpu_temp)

        # Update Flusk variables
        sensor_data["highest_sensor_temp"] = highest_sensor_temp
        sensor_data["gpu_temp"] = gpu_temp
        sensor_data["mean_fan_speed"] = mean_fan_speed
        sensor_data["status"] = "OK"

        # Log information
        logging.info(f"Heat of Highest Temp Sensor: {highest_sensor_temp}C")
        logging.info(f"Mean Fan Speed: {mean_fan_speed} RPM")
        logging.info(f"GPU Temperature: {gpu_temp}C")

        # Get color pairs for display
        sensor_temp_color = get_color_for_value(highest_sensor_temp, "temperature")
        fan_speed_color = get_color_for_value(mean_fan_speed, "fan_speed")
        gpu_temp_color = get_color_for_value(gpu_temp, "temperature")

        # Display information (only if using curses)
        if use_curses:
            max_y, max_x = stdscr.getmaxyx()
            if max_x < 90:
                stdscr.addstr(0, 0, f"Terminal too small!", curses.color_pair(3))
            else:
                stdscr.addstr(
                    0,
                    0,
                    f"Highest Temperature for Board or CPUs: {highest_sensor_temp}C ",
                    curses.color_pair(sensor_temp_color),
                )
                stdscr.addstr(
                    0,
                    60,
                    f"Mean Fan Speed: {mean_fan_speed} RPM ",
                    curses.color_pair(fan_speed_color),
                )
                stdscr.addstr(
                    0,
                    90,
                    (
                        f"GPU Temperature: {gpu_temp}C"
                        if gpu_temp is not None
                        else "GPU Temperature: N/A"
                    ),
                    curses.color_pair(gpu_temp_color),
                )

            for i in range(max(len(corrected_temp_info), len(fan_info))):
                stdscr.addstr(i + 2, 58, "|", curses.color_pair(1))

            for idx, temp_line in enumerate(corrected_temp_info):
                stdscr.addstr(idx + 2, 0, f"{temp_line:<54}")

            spinner_idx = (spinner_idx + 1) % len(spinner_states)
            stdscr.addstr(
                len(corrected_temp_info) + 4,
                0,
                f"Running {spinner_states[spinner_idx]}",
                curses.color_pair(5),
            )

            for idx, fan_line in enumerate(fan_info):
                stdscr.addstr(idx + 2, 60, f"{fan_line:<54}")

            stdscr.refresh()

        else:
            print(
                f"Sensor: {highest_sensor_temp}C | GPU: {gpu_temp}C | Fan: {mean_fan_speed} RPM"
            )

        # Adjust fan speed based on temperature
        if max_temp <= 38:
            set_fan_speed(0x10)  # Lowest speed
        elif max_temp <= 44:
            set_fan_speed(0x20)  # New speed
        elif max_temp <= 50:
            set_fan_speed(0x30)  # Medium speed
        elif max_temp <= 60:
            set_fan_speed(0x40)  # New speed
        elif max_temp <= 70:
            set_fan_speed(0x50)  # High speed
        else:
            set_fan_speed(0x70)  # Maximum speed

        if use_curses:
            # Exit on 'q' key press
            c = stdscr.getch()
            if c == ord("q"):
                break


# Flask router
@app.route("/status", methods=["GET"])
def get_status():
    return jsonify(sensor_data)


# Run flask in a thread
def run_flask():
    app.run(host="0.0.0.0", port=8080)


# If not using curses, just run the main logic without UI
if __name__ == "__main__":
    if use_curses:
        curses.wrapper(main)
    else:
        main(None)  # For non-curses mode, just run the logic

    # create and start flask thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = (
        True  # daemon thread to make sure flask thread ends when main thread ends
    )
    flask_thread.start()
