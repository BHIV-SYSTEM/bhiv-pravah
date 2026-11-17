import traceback, observer_server
print('Starting loop')
try:
    observer_server._poll_loop(1)
except Exception as e:
    print('Error:')
    traceback.print_exc()
