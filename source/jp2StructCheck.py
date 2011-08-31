#! /usr/bin/env python
#
#
# 
# jp2StructCheck version 31 August 2011
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
#
# ISSUES:
# 1. Using wildcards on the command line doesn't result in the expected
# behaviour under Linux! Workaround: wrap them in quotes, e.g:
#
#  jp2StructCheck.py *  -- only processes 1st encountered file!
#  jp2StructCheck.py "*" -- results in correct behaviour 
#

import sys
import os
import imp
import glob
import struct
import argparse

scriptPath,scriptName=os.path.split(sys.argv[0])

__version__= "31 August 2011"

  
def main_is_frozen():
    return (hasattr(sys, "frozen") or # new py2exe
            hasattr(sys, "importers") # old py2exe
            or imp.is_frozen("__main__")) # tools/freeze

def get_main_dir():
    if main_is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(sys.argv[0])
    
def errorExit(msg):
    msgString=("ERROR (%s):  %s\n") % (scriptName,msg)
    sys.exit(msgString)

def printWarning(msg):
    msgString=("WARNING (%s):  %s\n") % (scriptName,msg)
    sys.stderr.write(msgString)
        
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
    outString='"%s",%s,%s\n' % (file,allRequiredBoxesFoundFlag,codestreamCompleteFlag)
    sys.stdout.write(outString)

def outputVerbose(file,allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes):
    # Print verbose output to stdout
    
    outString=('File name: "%s"\n') % (file)
    sys.stdout.write(outString)
    
    outString=('  Found all required boxes: %s\n') % (allRequiredBoxesFoundFlag)
    sys.stdout.write(outString)
    
    outString=('  Found end of codestream marker: %s\n') % (codestreamCompleteFlag)
    sys.stdout.write(outString)
    
    if allRequiredBoxesFoundFlag == False:
        outString="  Missing boxes:\n"
        sys.stdout.write(outString)
        for i in range(len(missingBoxes)):
            outString="   " + bytes.decode(missingBoxes[i]) + "\n"
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
    if cTrailingBytes==b'\xff\xd9':
        codestreamComplete=True
    else: codestreamComplete=False
    
    return(codestreamComplete)

def checkRequiredBoxes(boxTypes):
    # Verify if list boxTypes contains identifiers of all top-level
    # boxes that are required (compulsary) in JP2
    
    # Create list with marker codes that identify required boxes
    reqBoxes=[]
    reqBoxes.append(b'\x6a\x50\x20\x20') # Signature box
    reqBoxes.append(b'\x66\x74\x79\x70') # File Type box
    reqBoxes.append(b'\x6a\x70\x32\x68') # JP2 Header box
    reqBoxes.append(b'\x6a\x70\x32\x63') # Contiguous Codestream box
      
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
        if boxType == b'\x6a\x70\x32\x63':
            codestreamCompleteFlag=checkCodestreamCompleteness(boxContents)
                    
        boxTypes.append(boxType)
           
        byteStart = byteEnd
    
    # Verify that all required top level boxes exist
    allRequiredBoxesFoundFlag, missingBoxes=checkRequiredBoxes(boxTypes)
       
    return(allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes)

        
def checkFiles(images,verboseOutputFlag):
    noFiles=len(images)
    
    if noFiles==0:
        printWarning("no images to check!")
        
    for i in range(noFiles):
        thisFile=images[i]
        isFile=os.path.isfile(thisFile)
        
        if isFile==True:
            fileData=readFileBytes(thisFile)
            allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes=checkJP2(fileData)
    
            # Output to screen
            if verboseOutputFlag ==True:
                outputVerbose(thisFile,allRequiredBoxesFoundFlag,codestreamCompleteFlag,missingBoxes)
            else:
                outputTerse(thisFile,allRequiredBoxesFoundFlag,codestreamCompleteFlag)
    
  
def parseCommandLine():
    # Create parser
    parser = argparse.ArgumentParser(description="Verify structure of JP2 image",version=__version__)
 
    # Add arguments
    parser.add_argument('jp2In', action="store", help="path to input JP2 image(s)")
    parser.add_argument('-t', action="store_false", dest="verboseOutputFlag", default=True, help="report output in terse format")
   
    # Parse arguments
    args=parser.parse_args()
      
    return(args)
        
def main():
    # Get input from command line
    args=parseCommandLine()
    jp2In=args.jp2In
    verboseOutputFlag=args.verboseOutputFlag
    
    # Input images as file list
    imagesIn=glob.glob(jp2In)
   
    # Check file
    checkFiles(imagesIn,verboseOutputFlag)
    
if __name__ == "__main__":
    main()


