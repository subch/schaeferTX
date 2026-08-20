import os, glob, time, openpyxl, xlrd, pyodbc, ctypes, sys
from pathlib import Path
from tkinter import *
from tkinter import ttk
from tkinter import filedialog as fd 
from tkinter import messagebox
# ----------------------------
# static variable definitions
timestr = time.strftime("%Y%m%d-%H%M%S")
filedt = time.strftime("%Y%m%d-%H%M%S")[4:8].lstrip("0")
col = 1
row = 1
ordernum = ''
specno = ''

# ----------------------------
# PATH HANDLING (PyInstaller safe)
# ----------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

INS_DIR = BASE_DIR / "ins_files"
HAMILTON_DIR = BASE_DIR / "hamilton files"

INS_DIR.mkdir(exist_ok=True)
HAMILTON_DIR.mkdir(exist_ok=True)
# connection string
cnxn = pyodbc.connect("Driver={SQL Server Native Client 10.0};"
                        "Server=YOUR_SQL_SERVER\\INSTANCE;"
                        "Database=YOUR_DATABASE;"
                        "UID=APOLLO_USER;"
                        "PWD=APOLLO_PASSWORD;")
cursor = cnxn.cursor()
# ----------------------------
# file header definition
tab = "\t"
file_headers = [
"% header=SampleName", "SampleID", "Type", "Comments", "AcqMethod", "ProcMethod", "RackCode", 
"PlateCode", "VialPos", "SmplInjVol", "DilutFact", "WghtToVol", "RackPos", "PlatePos", 
"SetName", "OutputFile", "_Instrument", "_Lot", "_Level", "_PlateID", "_QCNAME"]
title_options = [
    "Instrument",
    "Rack_Pos",
    "Plate_Pos", 
    "Stream",
    "MBN1", 
    "File_location"
]
# ----------------------------
# File select
def open_text_file(): 

    # Specify the file types 
    filetypes = (('text files', '*.xls'), 
                ('All files', '*.*')) 

    # Show the open file dialog by specifying path 
    f = fd.askopenfile(filetypes=filetypes, 
                    initialdir=HAMILTON_DIR)

    # Set file entry to blank before selecting file
    file_entry.delete(0, 'end')

    # Insert the text extracted from file in a textfield 
    file_entry.insert(0,str(os.path.abspath(f.name)))
# ----------------------------
# Register data from form
def register():
    # Get the user input from the form
    instrument = ins_val.get()
    rack_pos = rack_val.get()
    plate_pos = plate_val.get()
    method = method_val.get()
    stream = stream_val.get()
    MBN1 = str(MBN1_entry.get()).replace(" ", "") #str("607624") 
    MBN2 = str(MBN2_entry.get()).replace(" ", "").upper() #str("607634")
    plate_code = str(plate_code_entry.get()).replace(" ", "")
    file_location = ""
    file_location = file_entry.get()
    
    # error catching from validations
    validations = []
    
    # validate form data
    if instrument == "":
        validations.append(["ERROR","The instrument is invalid."])
    
    if rack_pos == "":
        validations.append(["ERROR","The rack position is invalid."])
    
    if plate_pos == "":
        validations.append(["ERROR","The plate position is invalid."])

    if method == "":
        validations.append(["ERROR","The method is invalid."])

    if stream == "":
        validations.append(["ERROR","The stream is invalid."])

    if plate_code == "":
        validations.append(["ERROR","The plate code is blank."])

    batchdata = []
    if not (os.path.exists(file_location)):
        validations.append(["ERROR","The file location is invalid."])
    else:
        batchdata = hamilton_intake(file_location)

    # validate MBN
    validations.append(MBNval(MBN1))
    if MBN2 != "X":
        validations.append(MBNval(MBN2))

    # validation check
    if any("ERROR" in x for x in validations):
        alert_window(validations)
    else:
        # pull all pbi sample data into a single list
        pbi = []
        pbitemp = []
        pbitemp = pbi_data(MBN1)
        for x in range(len(pbitemp)):
            pbi.append(pbitemp[x])
        if MBN2 != "X":            
            pbitemp = pbi_data(MBN2)
            for x in range(len(pbitemp)):
                pbi.append(pbitemp[x])        
                   
        # validate the batch data
        delindex = []
        warnings = []
        for x in range(len(batchdata)):
            if batchdata[x][2] in ("Liquid Level Error", "Not Executed Error"):
                warnings.append(["WARNING", "Specimen " + batchdata[x][0] + " had an error and has been removed.\nIf a sample, will need removed from MBN"])
                delindex.append([x])
        for x in range(len(delindex)):
            print(batchdata[delindex[x][0]])
            del batchdata[delindex[x][0]]
        if any("WARNING" in x for x in warnings):
            alert_window(warnings)


        tempval = batchval(batchdata, pbi)
        for x in range(len(tempval)):
            validations.append(tempval[x])
        if any("ERROR" in x for x in validations):
            alert_window(validations)
        else:
            # display alerts
            alert_window(validations)
            # write the file
            file_writer(instrument, rack_pos, plate_pos, method, stream, MBN1, MBN2, plate_code, file_location, batchdata, pbi)
# ----------------------------
# pull the data from the inputfile
def hamilton_intake(file_location):
    workbook = xlrd.open_workbook(file_location)
    sheet = workbook.sheet_by_name('Report')

    # intake sheet definitions
    batchdata = []
    data_col = []
    header = []

    # take in the header row [0] and find the position of the sampleID and position
    for col_index in range(sheet.ncols):
        header.append(sheet.cell(0,col_index).value)
    data_col.append(header.index("Asp Container BC"))
    data_col.append(header.index("Disp PosID"))
    data_col.append(header.index("Asp Status"))
        
    # interate through the sheet pulling values
    for (row_index) in range(sheet.nrows - 1):
        row_data = []
        for col_index in range(sheet.ncols):
            if col_index in data_col:
                row_data.append(sheet.cell(row_index + 1,col_index).value)
        # exclude non-valid data
        if row_data[0] != '-----':
            # swap positions of row_data to keep position in [1]
            row_data[1], row_data[2] = row_data[2], row_data[1]
            # parse position to number
            col_letter = row_data[1][0]
            row_number = row_data[1][1:]
            column_value = ord(col_letter.upper()) - 64  # Convert column letter to its ASCII value (A=65, B=66, ...)
            row_data[1] = (column_value - 1) * 12 + int(row_number)
            # convert float values to strings, removing the .0 float value
            if str(row_data[0])[-2:] == ".0":
                row_data[0] = str(row_data[0])[:-2]
            batchdata.append(row_data)
    return(batchdata)
# ----------------------------
# display alerts
def alert_window(alerts):
    # alert window to display run status
    WS_EX_TOPMOST = 0x40000
    windowTitle = "Validation Results"


    alert_msg = ""
    if any("NOTES" in x for x in alerts):
        alert_msg = alert_msg + "The following notes were generated during file build: \n"
    for x in range(len(alerts)):
        if alerts[x][0] == "NOTES":
            alert_msg = alert_msg + alerts[x][1] + "\n"
    if any("WARNING" in x for x in alerts):
        alert_msg = alert_msg + "The following warnings were generated, please use caution when loading: \n"
    for x in range(len(alerts)):
        if alerts[x][0] == "WARNING":
            alert_msg = alert_msg + "Warning: " + alerts[x][1] + "\n"
    if any("ERROR" in x for x in alerts):
        alert_msg = alert_msg + "The following errors must be corrected before batch data can be generated: \n"
    for x in range(len(alerts)):
        if alerts[x][0] == "ERROR":
            alert_msg = alert_msg + "Error: " + alerts[x][1] + "\n"
    if any("SUCCESS" in x for x in alerts):
        alert_msg = alert_msg + "The following data has been validated: \n"
    for x in range(len(alerts)):
        if alerts[x][0] == "SUCCESS":
            alert_msg = alert_msg + "Success: " + alerts[x][1] + "\n"
    # display a message box; execution will stop here until user acknowledges
    ctypes.windll.user32.MessageBoxExW(None, alert_msg, windowTitle, WS_EX_TOPMOST)

    print("User clicked OK.")
# ----------------------------
# validate MBN
def MBNval(MBN):
    val_query = "select top 1 * from pb where mbatch = '" + MBN + "' and bact = 1"
    cursor.execute(val_query)
    if cursor.fetchone() is None:
        return(["ERROR", "The MBN " + MBN + " is not valid, please enter a valid MBN."])
    elif MBN == "":
        return(["ERROR", "The MBN is blank and must be updated."])
    else:
        return(["SUCCESS", "The MBN " + MBN + " has been validated."])
# ----------------------------
# validate the hamilton batch data aginst the pbi data
def batchval(batchdata, pbi):
    error_log = []
    samp_count = 0
    for x in range(len(pbi)):
        pspecno = str(pbi[x][0]) + str(pbi[x][1])
        if any(pspecno in y for y in batchdata):
            samp_count += 1
        else:
            error_log.append(["ERROR", "The specimen " + str(pbi[x][0]) + " is not present in the Hamilton Batch"])
    #print(error_log)
    if not error_log:
        error_log.append(["SUCCESS", "Hamilton and Apollo run data have both been validated. " + str(samp_count) + " samples have been checked."])
    
    
    return(error_log)
# ----------------------------
# pull pbi data
def pbi_data(MBN):
    pbi_query = ("select pspecno, pcont, mbatch from pbi "
                    "join pb on pb.batch = pbi.batch and pb.befdt = pbi.befdt "
                    "where mbatch = '" + MBN + "' and bact = 1 and qcid = '' and pspecno <> ''")
    cursor.execute(pbi_query)

    pbi_apollo = []
    for pbi_row in cursor:
        pbi_apollo.append(pbi_row)
    
    return(pbi_apollo)    
# ----------------------------
# pull QC data
def qc_query(MBN):

    query = ("select kqcruni.qcid, kqcruni.qcspecno from pb " 
            "join kqcrun on pb.pbbqcrun = kqcrun.qcrun " 
            "join kqcruni on kqcrun.qcrun = kqcruni.qcrun and kqcrun.qcrefdt = kqcruni.qcrefdt " 
            "where bact = 1 and mbatch = '" + str(MBN) + "' and pb.wl = kqcruni.wl")
    cursor.execute(query)

    qc_data = []
    for qc_row in cursor:
        qc_data.append(qc_row)
    
    return(qc_data)
# ----------------------------
# wash writer
def wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
               rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum):
    # write wash
    if wash == 0:
        negname = "NEG1"
        negqc = str(neg_loc[0][2])
    else:
        negname = "WASH-" + str(wash)
        negqc = "WASH-" + str(wash)
    file.write(negname + tab + negqc + tab + "QC" + tab + comments + tab + acc_method + ".dam" + tab +
               promethod + tab + rack_code + tab + plate_type + tab + str(neg_loc[0][1]) + tab + injvol + tab + dilution + tab + weight + tab + 
                rack_pos + tab + plate_pos + tab + setname + tab + outputfile + str("{0:03}".format(filenum)) + tab + instrument + tab +
                "NEG" + tab + "NEG" + tab + plate_code + tab + "NEG" 
                )
    file.write("\n")
    wash += 1
    filenum += 1
    return wash, filenum
# ----------------------------
# cal writer
def cal_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
              rack_pos, plate_pos, setname, outputfile, instrument, cals, filenum):
    # write the cal list
    calct= 1
    for calnum in range(len(cals)):
        file.write(str(cals[calnum][0])  + tab + str(cals[calnum][0]) + tab + "Standard" + tab + comments + tab + acc_method + ".dam" + tab +
               promethod + tab + rack_code + tab + plate_type + tab + str(cals[calnum][1]) + tab + injvol + tab + dilution + tab + weight + tab + 
                rack_pos + tab + plate_pos + tab + setname + tab + outputfile + str("{0:03}".format(filenum)) + tab + instrument + tab +
                "S"  + str(calct) + tab + "S" + str(calct)  + tab + plate_code + tab + "" 
                )
        file.write("\n")
        filenum += 1
        calct +=1
    return filenum
# ----------------------------
# QC writer
def QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
             rack_pos, plate_pos, setname, outputfile, instrument, qcs, filenum):
    qcct = 1
    for qcnum in range(len(qcs)):
        if "HYD" in str(qcs[qcnum][0]):
            qcname = "HYD"
        elif "QC" in str(qcs[qcnum][0]):
            qcname = "QC" + str(qcct)
        else:
            qcname = "Ext-1"
        
        file.write(str(qcs[qcnum][0])  + tab + str(qcs[qcnum][2]) + tab + "QC" + tab + comments + tab + acc_method + ".dam" + tab +
               promethod + tab + rack_code + tab + plate_type + tab + str(qcs[qcnum][1]) + tab + injvol + tab + dilution + tab + weight + tab + 
                rack_pos + tab + plate_pos + tab + setname + tab + outputfile + str("{0:03}".format(filenum)) + tab + instrument + tab +
                qcname + tab + qcname + tab + plate_code + tab + "" 
                )
        file.write("\n")
        filenum += 1
        if "QC" in str(qcs[qcnum][0]):
            qcct += 1
    return filenum
# ----------------------------
# sample writer
def sample_write(MBN, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum):
    # write samples
    for x in range(len(pbi)):
        if pbi[x][2] == MBN:
            #print(samples)
            #print(pbi[x])
            pspecno = str(pbi[x][0]) + str(pbi[x][1])
            pspec_loc = ""
            for y in range(len(samples)):
                if samples[y][0] == pspecno:
                    pspec_loc = str(samples[y][1])
            # if location not found in sample data then error reported as location
            if pspec_loc == "":
                pspec_loc = "ERROR"
            
            file.write(pspecno + tab + pspecno  + tab + "Unknown" + tab + comments + tab + acc_method + ".dam" + tab +
                promethod + tab + rack_code + tab + plate_type + tab + pspec_loc + tab + injvol + tab + dilution + tab + weight + tab + 
                    rack_pos + tab + plate_pos + tab + setname + tab + outputfile + str("{0:03}".format(filenum)) + tab + instrument + tab +
                    "" + tab + "" + tab + plate_code + tab + ""
            )
            file.write("\n")
            filenum += 1
    
    return filenum
# ----------------------------
# repeat writer
def repeat_write(MBN, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum):
    samplenotes = []
    # write samples
    for x in range(len(samples)):
        repeat = True
        for y in range(len(pbi)):
            pbispecno = str(pbi[y][0] + pbi[y][1])
            if pbispecno == samples[x][0]:
                repeat = False
        if repeat == True:
            pspecno = str(samples[x][0])
            pspec_loc = str(samples[x][1])

            file.write(pspecno + tab + pspecno  + tab + "Unknown" + tab + comments + tab + acc_method + ".dam" + tab +
                promethod + tab + rack_code + tab + plate_type + tab + pspec_loc + tab + injvol + tab + dilution + tab + weight + tab + 
                    rack_pos + tab + plate_pos + tab + setname + tab + outputfile + str("{0:03}".format(filenum)) + tab + instrument + tab +
                    "" + tab + "" + tab + plate_code + tab + ""
            )
            file.write("\n")
            filenum += 1
            samplenotes.append(["NOTES","Non-MBN sample " + pspecno + " in location " + pspec_loc + " added to batch."])
    
    return filenum, samplenotes
# ----------------------------
# file writer
def file_writer(instrument, rack_pos, plate_pos, method, stream, MBN1, MBN2, plate_code, file_location, batchdata, pbi):

    # define static file components
    acc_method = method + "_Str" + stream
    comments = ""
    promethod= "none"
    rack_code = "3 Drawer"
    if ("TOX3" in method) or (instrument == "LC_7"): 
        plate_type = "2x DW96"
    else: 
        plate_type = "Deep Well MTP 96 Cooled"
        rack_code = "Deep Well MTP 96 Cooled"
    injvol = "10"
    dilution = "1"
    weight = "0"
    setname = "SET1"
    qc_data = qc_query(MBN1)
    if MBN2 != "X":
        qc_data2 = qc_query(MBN2)

    # sort and organize hamilton data
    cals = []
    qcs = []
    neg_loc = []
    samples = []

    for x in range(len(batchdata)):
        if "CAL" in str(batchdata[x][0]):
            cals.append(batchdata[x])
        elif ("QC") in str(batchdata[x][0]):
            qcs.append(batchdata[x])
        elif ("EXT-1") in str(batchdata[x][0]):
            qcs.append(["Ext-1",batchdata[x][1]])
        elif "NEG" in str(batchdata[x][0]):
            neg_loc.append(batchdata[x])
        else:
            samples.append(batchdata[x])   
    
    # find samples not present in MBN
    


    # define combined file format
    if MBN2 == "X":
        MBN2x = ""
    else:
        MBN2x = "_" + MBN2
    outputfile = plate_code + "_" + MBN1 + MBN2x + "_" + filedt + "_" + acc_method + "_" + instrument + "-"
    
    # negative QC ID
    for y in range(len(qc_data)):
            tempdata = str(qc_data[y][0])
            if (tempdata == "NEG"):
                neg_loc[0] = (neg_loc[0][0], neg_loc[0][1], qc_data[y][1])
    
    # sort QCs and cals into correct numerical order
    cals.sort(key=lambda x: x[0])
    qcs.sort(key=lambda x: x[0])

    # make a new dir for each run
    filepath = str(INS_DIR) + "\\"+ plate_code + "_" + MBN1 + MBN2x + "_" + filedt + "_" + acc_method + "_" + instrument + "-" + time.strftime("%Y%m%d-%H%M%S")
    print(filepath)
    os.mkdir(filepath)
    
    #############################################################################################################

    # create first file
    if MBN2 != "X":    
        file = open(filepath + "\\" + plate_code + "_" + MBN1 + MBN2x + "_" + filedt + "_" + acc_method + "_" + instrument + ".txt", "x")

        # additional definitions
        wash = 0
        filenum = 1

        # write the headers to the file
        for x in range(len(file_headers)):
            file.write(file_headers[x])
            if x < (len(file_headers) - 1):
                file.write(tab)
        file.write("\n")



        # write first wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # write cals
        filenum = cal_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
                            rack_pos, plate_pos, setname, outputfile, instrument, cals, filenum)
        
        # get QC IDs for first set of QCs

        for x in range(len(qcs)):
            for y in range(len(qc_data)):
                tempdata = str(qc_data[y][0])
                if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] != "2"):
                    qcs[x] = (qcs[x][0], qcs[x][1],qc_data[y][1])

        # write first QCs
        filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
                weight, rack_pos, plate_pos, setname, outputfile, instrument, qcs, filenum)

        # write next wash 
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # write first set of samples
        filenum = sample_write(MBN1, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)
        
        #write second set of QCs
        # get QC IDs for second set of QCs
        tempqcs =[]
        for x in range(len(qcs)):
            for y in range(len(qc_data)):
                tempdata = str(qc_data[y][0])
                #print(tempdata)
                if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] == "2") and (tempdata.strip() != "HYD" or tempdata.strip() != "Ext-1"):
                    tempqcs.append([qcs[x][0], qcs[x][1],qc_data[y][1]])

        filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
                weight, rack_pos, plate_pos, setname, outputfile, instrument, tempqcs, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # write second set of samples
        # set MBN2 filenumber
        filenum_MBN2 = filenum
        filenum = sample_write(MBN2, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

        # write repeat/offline samples
        notes = []
        filenum, notes = repeat_write(MBN1, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)
        
        #write final set of QCs
        # get QC IDs for last set of QCs
        tempqcs = []
        for x in range(len(qcs)):
            for y in range(len(qc_data2)):
                tempdata = str(qc_data2[y][0])
                if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] == "2") and (tempdata != "HYD" or tempdata != "Ext-1"):
                    tempqcs.append([qcs[x][0], qcs[x][1],qc_data2[y][1]])
        filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
                weight, rack_pos, plate_pos, setname, outputfile, instrument, tempqcs, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)    
        
        # close the file
        file.close()

    ###########################################################################################################################################

    # create MBN1 file
    file = open(filepath + "\\" + plate_code + "_" + MBN1 + "_" + filedt + "_" + acc_method + "_" + instrument + ".txt", "x")

    # additional definitions
    wash = 0
    filenum = 1

    # write the headers to the file
    for x in range(len(file_headers)):
        file.write(file_headers[x])
        if x < (len(file_headers) - 1):
            file.write(tab)
    file.write("\n")

    # write first wash
    wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

    # write cals
    filenum = cal_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
                        rack_pos, plate_pos, setname, outputfile, instrument, cals, filenum)
    
    # get QC IDs for first set of QCs
    for x in range(len(qcs)):
        for y in range(len(qc_data)):
            tempdata = str(qc_data[y][0])
            if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] != "2"):
                qcs[x] = (qcs[x][0], qcs[x][1],qc_data[y][1])

    # write first QCs
    filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
             weight, rack_pos, plate_pos, setname, outputfile, instrument, qcs, filenum)

    # write next wash 
    wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

    # write samples
    filenum = sample_write(MBN1, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

    #write next wash
    wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

    # write repeat/offline samples
    if MBN2 == "X":
        notes = []
        filenum, notes = repeat_write(MBN1, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

    #write second set of QCs
    # get QC IDs for second set of QCs
    tempqcs = []
    for x in range(len(qcs)):
        for y in range(len(qc_data)):
            tempdata = str(qc_data[y][0])
            if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] == "2") and (tempdata.strip() != "HYD" or tempdata.strip() != "Ext-1"):
                tempqcs.append([qcs[x][0], qcs[x][1],qc_data[y][1]])
    filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
            weight, rack_pos, plate_pos, setname, outputfile, instrument, tempqcs, filenum)

    #write next wash
    wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

    # close the file
    file.close()

    #############################################################################################################
    
    # create MBN2 file
    if MBN2 != "X":
        file = open(filepath + "\\" + plate_code + "_" + MBN2 + "_" + filedt + "_" + acc_method + "_" + instrument + ".txt", "x")

        # additional definitions
        wash = 0
        filenum = 1

        # negative QC ID
        for y in range(len(qc_data2)):
                tempdata = str(qc_data2[y][0])
                if (tempdata == "NEG"):
                    neg_loc[0] = (neg_loc[0][0], neg_loc[0][1], qc_data2[y][1])

        # write the headers to the file
        for x in range(len(file_headers)):
            file.write(file_headers[x])
            if x < (len(file_headers) - 1):
                file.write(tab)
        file.write("\n")

        # write first wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # write cals
        filenum = cal_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, weight, 
                            rack_pos, plate_pos, setname, outputfile, instrument, cals, filenum)
        
        # get QC IDs for first set of QCs
        for x in range(len(qcs)):
            for y in range(len(qc_data2)):
                tempdata = str(qc_data2[y][0])
                if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] != "2"):
                    qcs[x] = (qcs[x][0], qcs[x][1],qc_data2[y][1])

        # write first QCs
        filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
                weight, rack_pos, plate_pos, setname, outputfile, instrument, qcs, filenum)

        # write next wash 
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # write samples
        filenum = filenum_MBN2
        filenum = sample_write(MBN2, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

        # write repeat/offline samples
        notes = []
        filenum, notes = repeat_write(MBN1, samples, file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                               dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, pbi, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)
        
        #write second set of QCs
        # get QC IDs for second set of QCs
        tempqcs = []
        for x in range(len(qcs)):
            for y in range(len(qc_data2)):
                tempdata = str(qc_data2[y][0])
                if (tempdata[0:2] in qcs[x][0]) and (tempdata[-1] == "2") and (tempdata.strip() != "HYD" or tempdata.strip() != "Ext-1"):
                    tempqcs.append([qcs[x][0], qcs[x][1],qc_data2[y][1]])
        filenum = QC_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, dilution, 
                weight, rack_pos, plate_pos, setname, outputfile, instrument, tempqcs, filenum)

        #write next wash
        wash, filenum = wash_write(file, neg_loc, comments, acc_method, promethod, rack_code, plate_code, plate_type, injvol, 
                                dilution, weight, rack_pos, plate_pos, setname, outputfile, instrument, wash, filenum)

        # close the file
        file.close()

        # display any notes
        alert_window(notes)
# ----------------------------
# Create the main tkinter window
root = Tk()
root.title("Batch Builder")
root.geometry('300x500')
# ----------------------------
# Create labels and entry fields for each input

# Instrument
ins_options = [ 
"LC_5", "LC_7", "LC_9", "LC_12", "LC_13", "LC_15", "LC_17", "LC_18", "LC_19", "LC_20", 
"LC_21", "LC_23", "LC_24", "LC_25", "LC_27", "LC_28"
] 
ins_val = StringVar()
instrument_label = Label(root, text="Instrument:")
instrument_label.pack()
instrument_entry = OptionMenu( root , ins_val , *ins_options ) 
instrument_entry.pack()

# Rack 
rack_options = [ 
    "1", 
    "2"
] 
rack_val =StringVar()
rack_pos_label = Label(root, text="Rack Position:")
rack_pos_label.pack()
rack_pos_entry = OptionMenu( root , rack_val , *rack_options ) 
rack_pos_entry.pack()

# Plate
plate_options = [ 
    "1", 
    "2", 
    "3"
] 
plate_val =StringVar()
plate_pos_label = Label(root, text="Plate Position:")
plate_pos_label.pack()
plate_pos_entry = OptionMenu( root , plate_val , *plate_options ) 
plate_pos_entry.pack()

# Method
method_options = [ 
    "TO4"
    ##, 
    ##"TO3", 
    ##"TO3b", 
    ##"PSY"
] 
method_val =StringVar()
method_label = Label(root, text="method:")
method_label.pack()
method_entry = OptionMenu( root , method_val , *method_options ) 
method_entry.pack()

# Stream
stream_options = [ 
    "1", 
    "2"
] 
stream_val =StringVar()
stream_label = Label(root, text="Stream:")
stream_label.pack()
stream_entry = OptionMenu( root , stream_val , *stream_options ) 
stream_entry.pack()

# MBN1
MBN1_label = Label(root, text="MBN1:")
MBN1_label.pack()
MBN1_entry = Entry(root)
MBN1_entry.pack()

#MBN2
MBN2_label = Label(root, text="MBN2 (enter X for a single MBN):")
MBN2_label.pack()
MBN2_entry = Entry(root)
MBN2_entry.pack()

# Plate Code
plate_code_label = Label(root, text="Plate Code:")
plate_code_label.pack()
plate_code_entry = Entry(root)
plate_code_entry.pack()

# Create an open file button 
file_label = Label(root, text="File Location:")
file_label.pack()
file_entry = Entry(root)
file_entry.pack()
open_button = ttk.Button(root, text='Open a File', command=open_text_file)
open_button.pack()

# Form registration
register_button = Button(root, text="Generate", command=register)
register_button.pack()

# quit button
Button(root, text="Quit", command=root.destroy).pack()

root.mainloop()