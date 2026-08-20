"""Verbatim behavioural port of the original bb_v1.py file generation.

Kept deliberately ugly and 1:1 with the original so it can be trusted as an
oracle. Its only job is to prove that tests/fixtures/apollo_fixture.json
reproduces the shipped sample output. The real implementation lives in
src/batchbuilder and is checked against the same shipped files independently.

Not shipped. Not imported by the application.
"""
import os

import xlrd

tab = "\t"
file_headers = [
    "% header=SampleName", "SampleID", "Type", "Comments", "AcqMethod",
    "ProcMethod", "RackCode", "PlateCode", "VialPos", "SmplInjVol", "DilutFact",
    "WghtToVol", "RackPos", "PlatePos", "SetName", "OutputFile", "_Instrument",
    "_Lot", "_Level", "_PlateID", "_QCNAME",
]


def hamilton_intake(file_location):
    workbook = xlrd.open_workbook(file_location)
    sheet = workbook.sheet_by_name("Report")
    batchdata, data_col, header = [], [], []
    for col_index in range(sheet.ncols):
        header.append(sheet.cell(0, col_index).value)
    data_col.append(header.index("Asp Container BC"))
    data_col.append(header.index("Disp PosID"))
    data_col.append(header.index("Asp Status"))
    for row_index in range(sheet.nrows - 1):
        row_data = []
        for col_index in range(sheet.ncols):
            if col_index in data_col:
                row_data.append(sheet.cell(row_index + 1, col_index).value)
        if row_data[0] != "-----":
            row_data[1], row_data[2] = row_data[2], row_data[1]
            col_letter = row_data[1][0]
            row_number = row_data[1][1:]
            column_value = ord(col_letter.upper()) - 64
            row_data[1] = (column_value - 1) * 12 + int(row_number)
            if str(row_data[0])[-2:] == ".0":
                row_data[0] = str(row_data[0])[:-2]
            batchdata.append(row_data)
    return batchdata


class Ctx:
    """The pile of positional arguments the original threaded through everything."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def wash_write(file, neg_loc, c, wash, filenum):
    if wash == 0:
        negname = "NEG1"
        negqc = str(neg_loc[0][2])
    else:
        negname = "WASH-" + str(wash)
        negqc = "WASH-" + str(wash)
    file.write(
        negname + tab + negqc + tab + "QC" + tab + c.comments + tab
        + c.acc_method + ".dam" + tab + c.promethod + tab + c.rack_code + tab
        + c.plate_type + tab + str(neg_loc[0][1]) + tab + c.injvol + tab
        + c.dilution + tab + c.weight + tab + c.rack_pos + tab + c.plate_pos
        + tab + c.setname + tab + c.outputfile + str("{0:03}".format(filenum))
        + tab + c.instrument + tab + "NEG" + tab + "NEG" + tab + c.plate_code
        + tab + "NEG"
    )
    file.write("\n")
    return wash + 1, filenum + 1


def cal_write(file, c, cals, filenum):
    calct = 1
    for calnum in range(len(cals)):
        file.write(
            str(cals[calnum][0]) + tab + str(cals[calnum][0]) + tab + "Standard"
            + tab + c.comments + tab + c.acc_method + ".dam" + tab + c.promethod
            + tab + c.rack_code + tab + c.plate_type + tab + str(cals[calnum][1])
            + tab + c.injvol + tab + c.dilution + tab + c.weight + tab
            + c.rack_pos + tab + c.plate_pos + tab + c.setname + tab
            + c.outputfile + str("{0:03}".format(filenum)) + tab + c.instrument
            + tab + "S" + str(calct) + tab + "S" + str(calct) + tab
            + c.plate_code + tab + ""
        )
        file.write("\n")
        filenum += 1
        calct += 1
    return filenum


def QC_write(file, c, qcs, filenum):
    qcct = 1
    for qcnum in range(len(qcs)):
        if "HYD" in str(qcs[qcnum][0]):
            qcname = "HYD"
        elif "QC" in str(qcs[qcnum][0]):
            qcname = "QC" + str(qcct)
        else:
            qcname = "Ext-1"
        file.write(
            str(qcs[qcnum][0]) + tab + str(qcs[qcnum][2]) + tab + "QC" + tab
            + c.comments + tab + c.acc_method + ".dam" + tab + c.promethod + tab
            + c.rack_code + tab + c.plate_type + tab + str(qcs[qcnum][1]) + tab
            + c.injvol + tab + c.dilution + tab + c.weight + tab + c.rack_pos
            + tab + c.plate_pos + tab + c.setname + tab + c.outputfile
            + str("{0:03}".format(filenum)) + tab + c.instrument + tab + qcname
            + tab + qcname + tab + c.plate_code + tab + ""
        )
        file.write("\n")
        filenum += 1
        if "QC" in str(qcs[qcnum][0]):
            qcct += 1
    return filenum


def sample_write(MBN, samples, file, c, pbi, filenum):
    for x in range(len(pbi)):
        if pbi[x][2] == MBN:
            pspecno = str(pbi[x][0]) + str(pbi[x][1])
            pspec_loc = ""
            for y in range(len(samples)):
                if samples[y][0] == pspecno:
                    pspec_loc = str(samples[y][1])
            if pspec_loc == "":
                pspec_loc = "ERROR"
            file.write(
                pspecno + tab + pspecno + tab + "Unknown" + tab + c.comments
                + tab + c.acc_method + ".dam" + tab + c.promethod + tab
                + c.rack_code + tab + c.plate_type + tab + pspec_loc + tab
                + c.injvol + tab + c.dilution + tab + c.weight + tab
                + c.rack_pos + tab + c.plate_pos + tab + c.setname + tab
                + c.outputfile + str("{0:03}".format(filenum)) + tab
                + c.instrument + tab + "" + tab + "" + tab + c.plate_code + tab
                + ""
            )
            file.write("\n")
            filenum += 1
    return filenum


def repeat_write(MBN, samples, file, c, pbi, filenum):
    samplenotes = []
    for x in range(len(samples)):
        repeat = True
        for y in range(len(pbi)):
            if str(pbi[y][0] + pbi[y][1]) == samples[x][0]:
                repeat = False
        if repeat:
            pspecno = str(samples[x][0])
            pspec_loc = str(samples[x][1])
            file.write(
                pspecno + tab + pspecno + tab + "Unknown" + tab + c.comments
                + tab + c.acc_method + ".dam" + tab + c.promethod + tab
                + c.rack_code + tab + c.plate_type + tab + pspec_loc + tab
                + c.injvol + tab + c.dilution + tab + c.weight + tab
                + c.rack_pos + tab + c.plate_pos + tab + c.setname + tab
                + c.outputfile + str("{0:03}".format(filenum)) + tab
                + c.instrument + tab + "" + tab + "" + tab + c.plate_code + tab
                + ""
            )
            file.write("\n")
            filenum += 1
            samplenotes.append([
                "NOTES",
                "Non-MBN sample " + pspecno + " in location " + pspec_loc
                + " added to batch.",
            ])
    return filenum, samplenotes


def write_headers(file):
    for x in range(len(file_headers)):
        file.write(file_headers[x])
        if x < (len(file_headers) - 1):
            file.write(tab)
    file.write("\n")


def resolve_first(qcs, qcd):
    for x in range(len(qcs)):
        for y in range(len(qcd)):
            t = str(qcd[y][0])
            if (t[0:2] in qcs[x][0]) and (t[-1] != "2"):
                qcs[x] = (qcs[x][0], qcs[x][1], qcd[y][1])


def resolve_second(qcs, qcd):
    out = []
    for x in range(len(qcs)):
        for y in range(len(qcd)):
            t = str(qcd[y][0])
            # NOTE: the original condition is `!= "HYD" or != "Ext-1"`, which is
            # always True. Reproduced verbatim; it is inert only because the
            # trailing-"2" test already excludes HYD and Ext-1.
            if (t[0:2] in qcs[x][0]) and (t[-1] == "2") and (
                t.strip() != "HYD" or t.strip() != "Ext-1"
            ):
                out.append([qcs[x][0], qcs[x][1], qcd[y][1]])
    return out


def file_writer(outdir, filedt, qc_lookup, instrument, rack_pos, plate_pos,
                method, stream, MBN1, MBN2, plate_code, batchdata, pbi):
    acc_method = method + "_Str" + stream
    rack_code = "3 Drawer"
    if ("TOX3" in method) or (instrument == "LC_7"):
        plate_type = "2x DW96"
    else:
        plate_type = "Deep Well MTP 96 Cooled"
        rack_code = "Deep Well MTP 96 Cooled"

    qc_data = qc_lookup(MBN1)
    qc_data2 = qc_lookup(MBN2) if MBN2 != "X" else None

    cals, qcs, neg_loc, samples = [], [], [], []
    for x in range(len(batchdata)):
        if "CAL" in str(batchdata[x][0]):
            cals.append(batchdata[x])
        elif "QC" in str(batchdata[x][0]):
            qcs.append(batchdata[x])
        elif "EXT-1" in str(batchdata[x][0]):
            qcs.append(["Ext-1", batchdata[x][1]])
        elif "NEG" in str(batchdata[x][0]):
            neg_loc.append(batchdata[x])
        else:
            samples.append(batchdata[x])

    MBN2x = "" if MBN2 == "X" else "_" + MBN2
    stem = (plate_code + "_" + MBN1 + MBN2x + "_" + filedt + "_" + acc_method
            + "_" + instrument)

    c = Ctx(comments="", acc_method=acc_method, promethod="none",
            rack_code=rack_code, plate_code=plate_code, plate_type=plate_type,
            injvol="10", dilution="1", weight="0", rack_pos=rack_pos,
            plate_pos=plate_pos, setname="SET1", outputfile=stem + "-",
            instrument=instrument)

    for y in range(len(qc_data)):
        if str(qc_data[y][0]) == "NEG":
            neg_loc[0] = (neg_loc[0][0], neg_loc[0][1], qc_data[y][1])

    cals.sort(key=lambda x: x[0])
    qcs.sort(key=lambda x: x[0])

    written = []
    filenum_MBN2 = None

    if MBN2 != "X":
        p = os.path.join(outdir, stem + ".txt")
        written.append(p)
        with open(p, "x", newline="\r\n") as file:
            wash, filenum = 0, 1
            write_headers(file)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = cal_write(file, c, cals, filenum)
            resolve_first(qcs, qc_data)
            filenum = QC_write(file, c, qcs, filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = sample_write(MBN1, samples, file, c, pbi, filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = QC_write(file, c, resolve_second(qcs, qc_data), filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum_MBN2 = filenum
            filenum = sample_write(MBN2, samples, file, c, pbi, filenum)
            filenum, _ = repeat_write(MBN1, samples, file, c, pbi, filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = QC_write(file, c, resolve_second(qcs, qc_data2), filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)

    p = os.path.join(outdir, plate_code + "_" + MBN1 + "_" + filedt + "_"
                     + acc_method + "_" + instrument + ".txt")
    written.append(p)
    with open(p, "x", newline="\r\n") as file:
        wash, filenum = 0, 1
        write_headers(file)
        wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
        filenum = cal_write(file, c, cals, filenum)
        resolve_first(qcs, qc_data)
        filenum = QC_write(file, c, qcs, filenum)
        wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
        filenum = sample_write(MBN1, samples, file, c, pbi, filenum)
        wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
        if MBN2 == "X":
            filenum, _ = repeat_write(MBN1, samples, file, c, pbi, filenum)
        filenum = QC_write(file, c, resolve_second(qcs, qc_data), filenum)
        wash, filenum = wash_write(file, neg_loc, c, wash, filenum)

    if MBN2 != "X":
        p = os.path.join(outdir, plate_code + "_" + MBN2 + "_" + filedt + "_"
                         + acc_method + "_" + instrument + ".txt")
        written.append(p)
        with open(p, "x", newline="\r\n") as file:
            wash, filenum = 0, 1
            for y in range(len(qc_data2)):
                if str(qc_data2[y][0]) == "NEG":
                    neg_loc[0] = (neg_loc[0][0], neg_loc[0][1], qc_data2[y][1])
            write_headers(file)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = cal_write(file, c, cals, filenum)
            resolve_first(qcs, qc_data2)
            filenum = QC_write(file, c, qcs, filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = filenum_MBN2
            filenum = sample_write(MBN2, samples, file, c, pbi, filenum)
            filenum, _ = repeat_write(MBN1, samples, file, c, pbi, filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)
            filenum = QC_write(file, c, resolve_second(qcs, qc_data2), filenum)
            wash, filenum = wash_write(file, neg_loc, c, wash, filenum)

    return written
