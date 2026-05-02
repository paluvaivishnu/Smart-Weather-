import traceback
try:
    with open('debug.log', 'w') as f:
        f.write('starting\n')
    import runpy
    runpy.run_path('app.py', run_name='__main__')
except Exception as e:
    with open('debug.log', 'a') as f:
        f.write(traceback.format_exc())
