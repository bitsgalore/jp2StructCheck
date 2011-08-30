#! /usr/bin/env python
#
#
# 
# jp2StructCheck version 30 August 2011
# Requires: Python 2.7 OR Python 3.2 or better
#
# Copyright (C) 2011 Johan van der Knijff, Koninklijke Bibliotheek - National Library of the Netherlands
#	
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import imp
import struct
import argparse

scriptPath,scriptName=os.path.split(sys.argv[0])

__version__= "30 August 2011"

  
def main_is_frozen():
    return (hasattr(sys, "frozen") or # new py2exe
            hasattr(sys, "importers") # old py2exe
            or imp.is_frozen("__main__")) # tools/freeze

def get_main_dir():
    if main_is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(sys.argv[0])
    
def errorExit(msg):
    msgString=("ERROR (%s):  %s") % (scriptName,msg)
    sys.stderr.write(msgString)
    sys.exit()
    
def checkFileExists(fileIn):
    # Check if file exists and exit if not
    if os.path.isfile(fileIn)==False:
        msg=fileIn + " does not exist!"
        errorExit(msg)

def readFileBytes(file):
    # Read file, return contents as a byte object
       
    # Open file
    f=open(file,"rb")

    # Put contents of file into a byte object.
    fileData=f.read()
    f.close()

    return(fileData)

def outputTerse(file,allRequiredBoxesFoundFlag,codestreamCompleteFlag):
    # Print terse output to stdout
    outString='"%s",%s,%s \n' % (file,allRequiredBoxesFoundFlag,codestreamCompleteFlag)
    sys.stdout.write(outString)

def outputVerbose(file,allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes):
    # Print verbose output to stdout
    
    outString=('File name: "%s"\n') % (file)
    sys.stdout.write(outString)
    
    outString=('Found all required boxes: %s\n') % (allRequiredBoxesFoundFlag)
    sys.stdout.write(outString)
    
    outString=('Found end of codestream marker: %s\n') % (codestreamCompleteFlag)
    sys.stdout.write(outString)
    
    if allRequiredBoxesFoundFlag == False:
        for i in range(len(missingBoxes)):
            outString="Did not find " + (bytes.decode(missingBoxes[i]) + " box\n")
            sys.stdout.write(outString)
        

def checkCodestreamCompleteness(jp2c):
    # Verify completeness of JPEG 2000 codestream
    # Returns True if codestream appears to be complete and False otherwise
    #
    # Assumption: codestream is complete if it ends with an 'end of codestream'
    # marker (not necessarily true for complex corruption / malformedness!)
    
    # Codestream size in bytes
    cSize=len(jp2c)
    
    # Last 2 bytes of codestream
    cTrailingBytes=jp2c[cSize-2:cSize]
    
    # Check match against end of codestream marker (0xFFd9)
    if cTrailingBytes=='\xff\xd9':
        codestreamComplete=True
    else: codestreamComplete=False
    
    return(codestreamComplete)

def checkRequiredBoxes(boxTypes):
    # Verify if list boxTypes contains identifiers of all top-level
    # boxes that are required (compulsary) in JP2
    
    # Create list with marker codes that identify required boxes
    reqBoxes=[]
    reqBoxes.append('\x6a\x50\x20\x20') # Signature box
    reqBoxes.append('\x66\x74\x79\x70') # File Type box
    reqBoxes.append('\x6a\x70\x32\x68') # JP2 Header box
    reqBoxes.append('\x6a\x70\x32\x63') # Contiguous Codestream box
    
    noReqBoxes=len(reqBoxes)
    
    # Names of missing boxes to output list
    missingBoxes=[]
    
    # Initialise flag
    allRequiredBoxesFoundFlag=True
       
    for i in range(noReqBoxes):
        thisReqBox=reqBoxes[i]
        
        if thisReqBox not in boxTypes:
            allRequiredBoxesFoundFlag=False
            missingBoxes.append(thisReqBox)
              
    return(allRequiredBoxesFoundFlag, missingBoxes)  

   
def checkBox(bytesData, byteStart, noBytes):
    
    # Check top-level JP2 box and return information on its
    # size, type and contents
    
    # Box headers
    boxLength=bytesData[byteStart:byteStart+4]
    boxType=bytesData[byteStart+4:byteStart+8]

    # Box length as integer (stored as big-endian!)
    boxLengthValue=struct.unpack(">I",boxLength)[0]

    # Read extended box length if value equals 1
    if boxLengthValue == 1:
        boxLengthXL=bytesData[byteStart+8:byteStart+16]
        boxLengthValue=struct.unpack(">Q",boxLengthXL)[0]
    
    # For the very last box in a file boxLengthValue may equal 0, so we need
    # to calculate actual value
    if boxLengthValue == 0:
        boxLengthValue=noBytes-byteStart
    
    # End byte for current box
    byteEnd=byteStart + boxLengthValue
    
    # This box as a byte object
    boxContents=bytesData[byteStart:byteEnd]
    
    return(boxLengthValue,boxType,byteEnd,boxContents)


def checkJP2(jp2Data):
    # Parses all top-level boxes in JP2 byte object and checks for
    # 1. Presence of all required top-level boxes
    # 2. Completeness of codestream
       
    noBytes=len(jp2Data)
    byteStart = 0
    bytesTotal=0
    
    # Dummy value 
    boxLengthValue=10
    
    # Initial value, needed if no code stream is found at all
    codestreamCompleteFlag=False
    
    # List for storing box type identifiers
    boxTypes=[]
    
    while byteStart < noBytes and boxLengthValue != 0:
 
        boxLengthValue, boxType, byteEnd, boxContents = checkBox(jp2Data,byteStart, noBytes)
        
        # Perform completeness check for contiguous codestream box
        if boxType == '\x6a\x70\x32\x63':
            codestreamCompleteFlag=checkCodestreamCompleteness(boxContents)
                    
        boxTypes.append(boxType)
           
        byteStart = byteEnd
    
    # Verify that all required top level boxes exist
    allRequiredBoxesFoundFlag, missingBoxes=checkRequiredBoxes(boxTypes)
       
    return(allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes)

def checkOneFile(file,verboseOutputFlag):
    checkFileExists(file)
    fileData=readFileBytes(file)
    allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes=checkJP2(fileData)
    
    # Output to screen
    if verboseOutputFlag ==True:
        outputVerbose(file,allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes)
    else:
        outputTerse(file,allRequiredBoxesFoundFlag,codestreamCompleteFlag)
    
  
def parseCommandLine():
    # Create parser
    parser = argparse.ArgumentParser(description="Verify structure of JP2 image",version=__version__)
 
    # Add arguments
    parser.add_argument('jp2In', action="store", help="input JP2 image")
    parser.add_argument('-t', action="store_false", dest="verboseOutputFlag", default=True, help="report output in terse format")
   
    # Parse arguments
    args=parser.parse_args()
    
    # Normalise all file paths
    args.jp2In=os.path.normpath(args.jp2In)
    
    return(args)
        
def main():
    # Get input from command line
    args=parseCommandLine()
    jp2In=args.jp2In
    verboseOutputFlag=args.verboseOutputFlag
       
    # Check file
    checkOneFile(jp2In,verboseOutputFlag)
    
if __name__ == "__main__":
    main()


