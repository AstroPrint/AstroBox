
import logging
import subprocess

class processesUtil():
        
    def findProcess(processId ):
        ps= subprocess.Popen("ps -ef | grep "+processId, shell=True, stdout=subprocess.PIPE)
        output = ps.stdout.read()
        ps.stdout.close()
        ps.wait()
        logging.info('OUTPUT')
        logging.info(output)
        return output

    def isProcessRunning(processId):
        
        nameProcess = processId
        
        lastChar = processId[len(processId)-1]
        processId = processId[:-1]
        processId = processId + '[' + lastChar + ']'
        
        output = self.findProcess( processId )
        logging.info('output')
        logging.info(output)
        
        logging.info('nameProcess')
        logging.info(nameProcess)
        
        if nameProcess in output:
            logging.info('SEARCH TRUE')
            return True
        else:
            logging.info('SEARCH FALSE')
            return False

def numOfFilesInDir(nameOfDir,nameOfFile):
	ps= subprocess.Popen("find " + nameOfDir + " -maxdepth 1 -name '" + nameOfFile + "' | wc -l", shell=True, stdout=subprocess.PIPE)
        output = (int)(ps.stdout.read())
        ps.stdout.close()
        ps.wait()
        logging.info('OUTPUT')
        logging.info(output)
        return output
