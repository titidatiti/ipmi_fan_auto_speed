# 使用 Python 3.9 镜像为基础镜像
FROM python:3.9

# 更新包列表并安装 ipmitool
RUN apt-get update && apt-get install -y ipmitool

# 安装 Flask
RUN pip install flask

# 暴露 Flask 服务端口
EXPOSE 8080
