"""Process device requests with FastAPI."""


from __future__ import annotations
import json
import subprocess
import sys
import logging
from typing import Any
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.wsgi import WSGIMiddleware
import uvicorn
from bairy.device import utils, configs, dash_app


def configure_app_logging(log_path: str):
  """Configure uvicorn default logging to save to file."""

  LC: dict[Any, Any] = uvicorn.config.LOGGING_CONFIG

  # changing default formatting
  LC['formatters']['access']['fmt'] = configs.LOG_FORMAT
  LC['formatters']['access']['datefmt'] = configs.DATE_FORMAT
  LC['formatters']['default']['fmt'] = configs.LOG_FORMAT
  LC['formatters']['default']['datefmt'] = configs.DATE_FORMAT

  # adding FileHandler to LOGGING_CONFIG
  LC['handlers']['default_file'] = {
      'formatter': 'default',
      'class': 'logging.FileHandler',
      'filename': log_path}
  LC['handlers']['access_file'] = {
      'formatter': 'access',
      'class': 'logging.FileHandler',
      'filename': log_path}

  # telling loggers to use the additional handler
  LC['loggers']['uvicorn']['handlers'].append('default_file')
  LC['loggers']['uvicorn.access']['handlers'].append('access_file')


utils.configure_logging(configs.LOG_PATH)
configure_app_logging(configs.LOG_PATH)
app = FastAPI()
app.mount('/plot', WSGIMiddleware(dash_app.dash_plot.server))
app.mount('/table', WSGIMiddleware(dash_app.dash_table.server))


@app.get('/')
async def root():
  """Redirect to plot."""
  return RedirectResponse(url='/plot')


@app.get('/data')
def data():
  """Return streaming response of CSV containing all data."""
  # cannot use with ... here
  f = open(configs.DATA_PATH, 'rb')
  return StreamingResponse(f, media_type='text/csv')


@app.get('/logs', response_class=PlainTextResponse)
async def logs():
  """Return app log as plain text."""
  with open(configs.LOG_PATH) as f:
    return f.read()


@app.get('/status', response_class=PlainTextResponse)
def status():
  """Return device status as plaintext json."""
  device_status = status_json()
  return json.dumps(device_status, indent=4)


@app.get('/status.json')
def status_json():
  """Return device status as raw json."""
  device_configs = configs.load_device().dict()
  size = utils.get_data_size()
  n_rows = utils.count_rows(utils.DATA_PATH)
  latest = utils.latest_data()
  device_status = {'device_configs': device_configs,
                   'data_details': {'file_size': size, 'n_rows': n_rows},
                   'latest_reading': latest}
  return device_status


@app.get('/remote/{command}', response_class=PlainTextResponse)
def remote(command: str):
  """Run remote command on device."""
  if command == 'reboot':
    logging.info('Reboot requested')
    try:
      subprocess.check_call(['sudo', 'reboot'])
    except subprocess.CalledProcessError as e:
      logging.error('Reboot failure')
      logging.error(e)
    return None

  if command == 'update':
    logging.info('Update requested')
    call = [sys.executable, '-m', 'pip', 'install', '-U', 'bairy']
    try:
      subprocess.check_call(call)
      logging.info('Update success')
      return 'success'
    except subprocess.CalledProcessError as e:
      logging.error('Update failure')
      logging.error(e)
      return 'fail'

  elif command == 'disk':
    logging.info('df requested')
    p = subprocess.Popen(['df', '-h'],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
      logging.error(err.decode())
    return out.decode()

  else:
    return 'unknown command'


def run_app():
  """Run app with uvicorn."""
  uvicorn.run(app, host='0.0.0.0', port=8000)
