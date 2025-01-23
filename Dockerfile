# 使用 Python 3.9 镜像为基础镜像
FROM python:3.9

# 更新包列表并安装 ipmitool
RUN apt-get update && apt-get install -y ipmitool
