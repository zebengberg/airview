"""Defining Sensor ABC and its derived classes."""

from __future__ import annotations
import random
import logging
from pydantic import BaseModel
import smbus2  # or just smbus
from gpiozero import MotionSensor
from pypeck.device.configs import DATE_FORMAT, LOG_PATH, LOG_FORMAT


def configure_sensor_logging():
  """Set up root logger to record sensoring reading errors."""
  root_logger = logging.getLogger()
  formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
  file_handler = logging.FileHandler(LOG_PATH)
  file_handler.setFormatter(formatter)
  root_logger.addHandler(file_handler)

  console_handler = logging.StreamHandler()
  console_handler.setFormatter(formatter)
  root_logger.addHandler(console_handler)


configure_sensor_logging()


class Sensor:
  """An abstract base class for sensors."""

  def __init__(self, configs: BaseModel, prev_reading: int | None = None):
    for k, v in configs.dict().items():
      setattr(self, k, v)
    self.prev_reading = prev_reading

  def read(self) -> dict[str, int | None]:
    """Read sensor measurements and return dictionary of values."""
    read_dict = {'air': self.read_air,
                 'random': self.read_random,
                 'ir': self.read_ir}
    return read_dict[self.sensor_type]()

  def read_air(self):
    """Read I2C data from air sensor."""

    keys_dict = {
        'pm_1.0': (4, 5),
        'pm_2.5': (6, 7),
        'pm_10': (8, 9),
        'n_beyond_0.3': (16, 17),
        'n_beyond_0.5': (18, 19),
        'n_beyond_1.0': (20, 21),
        'n_beyond_2.5': (22, 23),
        'n_beyond_5.0': (24, 25),
        'n_beyond_10': (26, 27)}
    data_dict: dict[str, int | None] = {k: None for k in keys_dict}

    with smbus2.SMBus(1) as bus:
      try:
        data: list[int] = bus.read_i2c_block_data(self.i2c_address, 0, 32)
      except OSError:  # couldn't read data -- sensor disconnected?
        logging.warning('Unable to connect to air sensor over I2C')
        return data_dict

      # start characters, check sum, error byte
      try:
        assert data[0] == 0x42
        assert data[1] == 0x4d
        assert data[29] == 0
      except AssertionError:
        logging.warning('Internal error on air sensor.')
      if sum(data[:30]) != (data[30] << 8) + data[31]:
        logging.warning('Bad checksum from air sensor.')

      for k, (byte1, byte2) in keys_dict.items():
        data_dict[k] = (data[byte1] << 8) + data[byte2]
    return data_dict

  def read_ir(self):
    """Read value associated to IR sensor digital pin."""
    m = MotionSensor(self.bcm_pin)
    v: int = m.value
    return {'ir_state': v}

  def read_random(self):
    """Create random data for testing device."""
    if self.prev_reading is None:
      r = random.randint(0, 255)
    else:
      r = self.prev_reading + random.randint(-3, 3)
      r = max(min(r, 255), 0)  # clipping
    self.prev_reading = r
    return {'random': r}
