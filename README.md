# **IPMI Fan Auto Speed**

This Docker-based solution monitors a remote server using IPMI and automatically manages fan speeds based on sensor and GPU temperatures in real-time. Additionally, it exposes a Flask-based status web page displaying the service status in JSON format.

**Forked from:** [cemdede/Fan_Adjustment_for_System_Temperature](https://github.com/cemdede/Fan_Adjustment_for_System_Temperature)

---

## Features

- **Remote server monitoring** using IPMI to check temperatures and fan speeds.
- **Real-time fan speed adjustment** based on CPU and GPU temperature readings.
- **Flask-based web page** to show the status of the system, with data in JSON format.
- **Easily deployable in Docker** and manageable via Portainer.

---

## Quick Start

You can easily deploy this solution as a **Portainer Stack** by configuring the following environment variables:

### Required Environment Variables:

- `**IPMI_IP**`: IP address of the remote server's IPMI interface.
- `**IPMI_USER**`: Username for the server's IPMI interface.
- `**IPMI_PASS**`: Password for the server's IPMI interface.
- `**CUSTOM_PORT**`: The port on which the status web page will be available.

Once the container is up and running, you can access the status page by visiting:
<your-docker-ip>:<CUSTOM_PORT>/status

For example, if your Docker host's IP address is `192.168.1.100` and you set `CUSTOM_PORT` to `8080`, the URL will be:

http://192.168.1.100:8080/status

### Example Status Output

When you visit the status page, you will see a JSON response like this:

```json
{
  "gpu_temp": 23,
  "highest_sensor_temp": 28.0,
  "mean_fan_speed": 3620,
  "status": "OK",
  "time": "2025-01-25 07:51:19"
}
```
