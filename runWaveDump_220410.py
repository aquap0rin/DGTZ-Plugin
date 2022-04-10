# =============================================================================
# FMISL Python plugin for WaveDump.exe 
# recent update : 220410_194108
#
# numSample : size of sampling window
# numEvent : target count
# PERSONAL_USE : Select Numpy or Binray / Activate telegram bot report
# =============================================================================

from numpy import linspace, unique, fromfile, save, array
from time import time, sleep, strftime, gmtime
from os import path, remove, mkdir, listdir
from datetime import datetime
from sys import argv
import win32console, subprocess
import telegram

PERSONAL_USE = True
telegramChatID = 0
telegramToken = 'None'

def sec2hms(sec): # time formating
    return strftime('%H:%M:%S', gmtime(sec))

def keyboardInput(c): # getch
    con_in = win32console.GetStdHandle(win32console.STD_INPUT_HANDLE)
    buf = win32console.PyINPUT_RECORDType(win32console.KEY_EVENT)
    buf.KeyDown, buf.RepeatCount, buf.Char = 1, 1, c
    con_in.WriteConsoleInput([buf])
    return None

def getCurrentCount(**kwargs): # return current count
    numSample = kwargs['numSample']
    try:
        return int(path.getsize('wave_0.dat') / 4 / numSample)
    except:
        return 0

def sendReport(message): # send progress report using telegram bot
    print('-' * 80 + '\n' + message + '\n' + '-' * 80)
    if PERSONAL_USE:
        try:
            bot = telegram.Bot(token = telegramToken)        
            bot.send_message(chat_id = telegramChatID, text = message)
        except:
            print('-- Reporting failed --\n')
    return None    

class progressMonitor(): # checkpoints
    def __init__(self, numEvent, numUpdate = 5):
        self.points = unique(linspace(0, numEvent, numUpdate + 1).astype('int32'))[1:] # check points
        return None
    def report(self, count, numEvent, elapsed, ETA):
        if len(self.points):
            if self.points[0] < count:
                sendReport(f'{count:4d} / {numEvent:4d}\n{sec2hms(elapsed):s}\n{sec2hms(ETA):s}')
                self.points = self.points[self.points > count]
        return None

def saveAsDatOrNumpy(fileName, numSample, numEvent, resultPath): # result parsing
    ret = fromfile(fileName, dtype = 'float32')
    ret = ret[:numSample * numEvent]
    retName = path.join(resultPath, fileName) # new name
    if PERSONAL_USE == True:
        save(retName.replace('.dat', ''), ret.reshape(-1, numSample))
    else:
        ret.tofile(retName)
    print(f'{fileName:40s} -> {retName:40s}')
    if path.getsize(retName)  != numEvent * numSample * 4:
        print('ERROR: Unexpected error occurred while file transfer !! Check the Original file.')
    else:
        remove(fileName)
    return None

def postProcessing(**kwargs): # prase *.dat file    
    numSample, numEvent = kwargs['numSample'], kwargs['numEvent']
    resultPath = './' + datetime.now().strftime("%y%m%d_%H%M%S")
    mkdir(resultPath)    
    [saveAsDatOrNumpy(fileName, numSample, numEvent, resultPath) for fileName in listdir() if '.dat' in fileName]
    return resultPath    

def runWaveDump(**kwargs):    

    numEvent = kwargs['numEvent']    
    prog = progressMonitor(numEvent)
    timeFlags = []

    # clear previous results
    prevResult = lambda x : ('wave_' in x or 'TR_' in x) and '.dat' in x
    for fileName in listdir():
        if prevResult(fileName):
            try:
                remove(fileName)
            except:
                continue
    
    # run wavedump
    proc = subprocess.Popen('WaveDump.exe', shell = True, stdin = subprocess.PIPE)
    sleep(1)
    keyboardInput('s') # start DAQ
    sleep(1)
    keyboardInput('W') # start Writing

    # main loop
    count_old = 0
    tic = time()
    while True:
        sleep(1)
        count = getCurrentCount(**kwargs)
        remain = numEvent - count
        toc = time()
        elapsed = toc - tic

        # update time flags
        for _ in range(count_old, count):
            timeFlags.append(elapsed)

        # end DAQ
        if count > numEvent:
            keyboardInput('W') # end Writing
            while True: # end process
                keyboardInput('q')
                sleep(0.5)
                if proc.poll() is not None:
                    break
            print('End of Data acqusition')
            break

        # progress report
        ETA = remain / (count + 1e-9) * elapsed
        print(f'- elapsed : {elapsed:8.1f} s | count : {count:8d} / {numEvent:8d} | ETA : {ETA:8.1f} s', end = '\r')
        if count_old != count:            
            count_old = count
            prog.report(count = count, numEvent = numEvent, elapsed = elapsed, ETA = ETA)

    return array(timeFlags[:numEvent], dtype = 'float32')

if __name__ == '__main__':

    # setup
    numSample = int(argv[1])
    numEvent = int(argv[2])
    kwargs = {'numSample' : numSample, 'numEvent' : numEvent}

    # run Wave Dump
    timeFlags = runWaveDump(**kwargs)

    # run Post Processing
    resultPath = postProcessing(**kwargs)

    # save timeflags
    if PERSONAL_USE == True:
        save(path.join(resultPath, 'timeFlag'), timeFlags)
    else:
        timeFlags.tofile(path.join(resultPath, 'timeFlag.dat'))

    # report    
    cps = numEvent / timeFlags[-1]
    report = f'- Elapsed Time : {sec2hms(timeFlags[-1]):s}\n- total count : {numEvent:d}\n- cps {cps:.4f}'
    sendReport(report)
