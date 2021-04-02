from datetime import datetime
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
import click
import copy
import json
import requests
import sys
import threading
import time

# Default device data structure
data = {
    'event': {
        'device_boot': 0,
        'manipulation': 0,
        'pir_motion': 0,
        'reed_switch_1': {
            'activation': 0,
            'deactivation': 0,
        },
        'reed_switch_2': {
            'activation': 0,
            'deactivation': 0,
        },
    },
    'state': {
        'batt_voltage': 3.0,
        'humidity': None,
        'illuminance': None,
        'orientation': None,
        'reed_switch_1': 0,
        'reed_switch_2': 0,
        'temperature': None,
    }
}

# Synchronization objects
lock = threading.RLock()
sem = threading.Semaphore(0)
stop = threading.Event()


# Send worker function
def send_worker(device, interval, endpoint):
    while True:
        sem.acquire(blocking=True, timeout=interval)
        if stop.is_set():
            return
        with lock:
            payload = {
                'device': device,
                'data:': copy.deepcopy(data)
            }
            data['event']['device_boot'] = 0
        output = json.dumps(payload, indent=2)
        with open('sticker_reports', 'a') as writer:
            dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            template = '\n=================== {} ===================\n\n{}\n'
            writer.write(template.format(dt, output))
        if endpoint is not None:
            try:
                requests.post(endpoint, json=payload)
            except requests.RequestException:
                print(HTML('<orangered>HTTP request failed</orangered>'))


worker = None


# Application entrypoint
@click.command()
@click.option('-d', '--device', required=True, help='Unique device identifier.')
@click.option('-i', '--interval', default=900, type=int, help='Number of seconds between periodic sensor updates.')
@click.option('-e', '--endpoint', help='URL endpoint for sending API requests.')
@click.option('-s', '--script', type=click.Path(exists=True), help='Path to automation script (shell is not provided).')
def main(device, interval, endpoint, script):

    global worker

    # Start send worker
    worker = threading.Thread(target=send_worker, args=(device, interval, endpoint), daemon=True)
    worker.start()

    cd = CommandDispatcher()

    # General commands
    cd.add_cmd('exit', parser=None, handler=do_exit)
    cd.add_cmd('quit', parser=None, handler=do_exit)
    cd.add_cmd('send', parser=None, handler=do_send)
    cd.add_cmd('delay = ', parser=IntParser(1, 86400), handler=do_delay)

    # Trigger commands
    cd.add_cmd('device_boot', parser=None, handler=trigger_device_boot)
    cd.add_cmd('manipulation', parser=None, handler=trigger_manipulation)
    cd.add_cmd('pir_motion', parser=None, handler=trigger_pir_motion)

    # Setter commands
    cd.add_cmd('batt_voltage = ', parser=FloatParser(0, 4.0), handler=set_batt_voltage)
    cd.add_cmd('humidity = ', parser=FloatParser(0, 100, 1), handler=set_humidity)
    cd.add_cmd('illuminance = ', parser=IntParser(0, 83000), handler=set_illuminance)
    cd.add_cmd('orientation = ', parser=IntParser(1, 6), handler=set_orientation)
    cd.add_cmd('reed_switch_1 = ', parser=IntParser(0, 1), handler=set_reed_switch_1)
    cd.add_cmd('reed_switch_2 = ', parser=IntParser(0, 1), handler=set_reed_switch_2)
    cd.add_cmd('temperature = ', parser=FloatParser(-40, 85, 2), handler=set_temperature)

    # Prioritize script execution over shell
    if script is not None:
        with open(script) as f:
            for line, cmd in enumerate(f):
                cmd = cmd.strip()
                if len(cmd) == 0:
                    continue
                if not cd.dispatch(cmd):
                    print(HTML('<orangered>Invalid command (line {})</orangered>'.format(line + 1)))
                    sys.exit(1)
        do_exit()

    # Pass list of all commands to completer
    completer = WordCompleter(cd.get_prefixes())

    # Support prompt session with command history from file
    session = PromptSession(history=FileHistory('sticker_history'))

    # Process prompt commands in loop
    while True:
        cmd = session.prompt(HTML('<steelblue><b>sticker> </b></steelblue>'),
                             completer=completer,
                             complete_while_typing=True,
                             auto_suggest=AutoSuggestFromHistory())

        # Strip whitespace
        cmd = cmd.strip()

        # No processing for dummy commands
        if len(cmd) == 0:
            continue

        # Dispatch command
        if not cd.dispatch(cmd):
            print(HTML('<orangered>Invalid command</orangered>'))


def do_exit():
    stop.set()
    sem.release()
    worker.join()
    sys.exit(0)


def do_send():
    sem.release()


def do_delay(value):
    time.sleep(value)


def trigger_device_boot():
    with lock:
        data['event']['device_boot'] = 1
        sem.release()


def trigger_manipulation():
    with lock:
        data['event']['manipulation'] += 1
        if data['event']['manipulation'] > 65535:
            data['event']['manipulation'] = 0
        sem.release()


def trigger_pir_motion():
    with lock:
        data['event']['pir_motion'] += 1
        if data['event']['pir_motion'] > 65535:
            data['event']['pir_motion'] = 0
        sem.release()


def set_batt_voltage(value):
    with lock:
        data['state']['batt_voltage'] = value


def set_humidity(value):
    with lock:
        data['state']['humidity'] = value


def set_illuminance(value):
    with lock:
        data['state']['illuminance'] = value


def set_orientation(value):
    with lock:
        data['state']['orientation'] = value


def set_reed_switch_1(value):
    with lock:
        if data['state']['reed_switch_1'] == 0 and value == 1:
            data['event']['reed_switch_1']['activation'] += 1
            if data['event']['reed_switch_1']['activation'] > 65535:
                data['event']['reed_switch_1']['activation'] = 0
            data['state']['reed_switch_1'] = 1
            sem.release()
        elif data['state']['reed_switch_1'] == 1 and value == 0:
            data['event']['reed_switch_1']['deactivation'] += 1
            if data['event']['reed_switch_1']['deactivation'] > 65535:
                data['event']['reed_switch_1']['deactivation'] = 0
            data['state']['reed_switch_1'] = 0
            sem.release()


def set_reed_switch_2(value):
    with lock:
        if data['state']['reed_switch_2'] == 0 and value == 1:
            data['event']['reed_switch_2']['activation'] += 1
            if data['event']['reed_switch_2']['activation'] > 65535:
                data['event']['reed_switch_2']['activation'] = 0
            data['state']['reed_switch_2'] = 1
            sem.release()
        elif data['state']['reed_switch_2'] == 1 and value == 0:
            data['event']['reed_switch_2']['deactivation'] += 1
            if data['event']['reed_switch_2']['deactivation'] > 65535:
                data['event']['reed_switch_2']['deactivation'] = 0
            data['state']['reed_switch_2'] = 0
            sem.release()


def set_temperature(value):
    with lock:
        data['state']['temperature'] = value


class IntParser:

    def __init__(self, min=None, max=None):
        self._min = min
        self._max = max

    def parse(self, value):
        try:
            value = int(value)
        except ValueError:
            return None
        if self._min is not None:
            if value < self._min:
                return None
        if self._max is not None:
            if value > self._max:
                return None
        return value


class FloatParser:

    def __init__(self, min=None, max=None, decimals=None):
        self._min = min
        self._max = max
        self._decimals = decimals

    def parse(self, value):
        try:
            value = float(value)
        except ValueError:
            return None
        if self._decimals is not None:
            value = round(value, self._decimals)
        if self._min is not None:
            if value < self._min:
                return None
        if self._max is not None:
            if value > self._max:
                return None
        return value


class CommandDispatcher:

    def __init__(self):
        self._cmds = []

    def add_cmd(self, prefix, parser=None, handler=None):
        cmd = {}
        cmd['prefix'] = prefix
        cmd['parser'] = parser
        cmd['handler'] = handler
        self._cmds.append(cmd)

    def get_prefixes(self):
        prefixes = []
        for cmd in self._cmds:
            prefixes.append(cmd['prefix'])
        return prefixes

    def dispatch(self, input):
        for cmd in self._cmds:
            if input.startswith(cmd['prefix']):
                if cmd['parser'] is not None:
                    value = cmd['parser'].parse(input[len(cmd['prefix']):])
                    if value is None:
                        return False
                    if cmd['handler'] is not None:
                        cmd['handler'](value)
                    return True
                else:
                    if len(input) != len(cmd['prefix']):
                        return False
                    if cmd['handler'] is not None:
                        cmd['handler']()
                return True
        return False


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
