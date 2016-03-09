
import logging
import subprocess

def findProcess(processId ):
    ps= subprocess.Popen("ps -ef | grep "+processId, shell=True, stdout=subprocess.PIPE)
    output = ps.stdout.read()
    ps.stdout.close()
    ps.wait()
    return output

def isProcessRunning(processId):
    
    nameProcess = processId
    
    lastChar = processId[len(processId)-1]
    processId = processId[:-1]
    processId = processId + '[' + lastChar + ']'
    
    output = findProcess( processId )
    
    if nameProcess in output:
        return True
    else:
        return False
