import pytesseract
import cv2
import math
import warnings
import numpy as np
from PIL import Image
from os import makedirs
import pandas as pd
#-----------------------------
# PED Data Frame Object Class
#-----------------------------
#TODO implement class for PED file dataframes


#-----------------------------
# PED FILE EXPORT
#-----------------------------
def PED_export(PED_df, output_dir = '.'):
    '''
    Writes a PED file-formatted dataframe to output_dir/<FamilyID>.ped and returns the file's path
    '''
    FamID = PED_df['FamilyID'].iloc[0]
    makedirs(output_dir, exist_ok= True)
    path = f'{output_dir}/{FamID}.ped'
    PED_df.to_csv(path_or_buf= path,
                  sep = '\t',
                  header= False,
                  index= False)
    return path

#-----------------------------
# IMAGE ENHANCEMENT
#-----------------------------
def _resample_filter():
    return Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS

def image_enhance(FamID, input_dir, upscale_factor = 10):
    '''
    Intakes raw pedigree image file and upscales for downstream analysis

    PARAMETERS:
    -----------
    FamID (string): ID denoting the particular pedigree for intake (should match PNG file name exactly)
    input_dir (string): file path where input pedigree image is found
    upscale_factor (int): the degree to which the raw pedigree image should be upscaled (default = 10)

    RETURN:
    -------
    output_path (string): complete file path from wd to upscaled image
    '''
    input_path = f'{input_dir}/{FamID}.png'

    img = Image.open(input_path)

    new_size = (img.width * upscale_factor, img.height * upscale_factor)
    upscaled_img = img.resize(new_size, _resample_filter())
    output_path = f'{input_dir}/{FamID}_{upscale_factor}Xupscaled.png'
    upscaled_img.save(output_path)
    return output_path

def upscaled_image(image_path, upscale_factor = 10):
    '''
    Reads a pedigree image and upscales it in memory, without writing a copy next to it

    RETURN:
    -------
    the upscaled image as an OpenCV (BGR) array
    '''
    img = Image.open(image_path).convert('RGB')
    new_size = (round(img.width * upscale_factor), round(img.height * upscale_factor))
    upscaled_img = img.resize(new_size, _resample_filter())
    return cv2.cvtColor(np.array(upscaled_img), cv2.COLOR_RGB2BGR)

def linDist(coord1, coord2):
    x1, y1 = coord1
    x2, y2 = coord2

    return((x2-x1)**2+(y2-y1)**2)**0.5


def closestLabel(marker_coords, label_dict):
    closest_distance = math.inf
    closestLabel = None
    for label in label_dict.keys():
        label_x, label_y, label_w, label_h = label_dict[label]['label_coords']
        label_coords = ((label_x + label_w/2), (label_y + label_h/2))
        distance = linDist(marker_coords, label_coords)
        if distance < closest_distance:
            closest_distance = distance
            closestLabel = label
    return closestLabel


#-----------------------------
# SYMBOL DETECTION
#-----------------------------
def stroke_width(dark_mask):
    '''
    Estimates the width of the drawing's lines from a mask of its dark pixels (255 where dark).
    Most runs of dark pixels across a row or down a column cross a line, so the most common run length is the line width.
    '''
    runs = []
    for arr in (dark_mask, dark_mask.T):
        step = max(1, arr.shape[0] // 400)
        for row in arr[::step]:
            dark = np.concatenate(([0], (row > 0).astype(np.int8), [0]))
            edges = np.flatnonzero(np.diff(dark))
            runs.extend((edges[1::2] - edges[0::2]).tolist())
    if not runs:
        return 1
    counts = np.bincount(runs)
    return max(1, int(np.argmax(counts)))

def symbol_sex(contour):
    '''
    Sex from a symbol's shape: a circle is female (2), a square male (1) and a diamond of unknown sex (0).
    A circle fills about 79% (pi/4) of the smallest rectangle around it, at any angle, where a square or a diamond
    fills nearly all of it. A square also fills its upright bounding box, but a diamond only fills half of its box.
    Measuring areas rather than counting corners copes with ragged outlines, as in a JPEG or a scan,
    and with corners rounded off.
    '''
    area = cv2.contourArea(contour)
    (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
    _, _, w, h = cv2.boundingRect(contour)
    if not (rw and rh and w and h):
        return 0
    if area / (rw * rh) < 0.89:
        return 2
    return 1 if area / (w * h) > 0.8 else 0

def open_with_disc(mask, radius):
    '''
    Morphological opening of a mask (255 where set) with a disc of the given radius: what is left is every part that
    a disc of that size fits inside. Done with two distance transforms, which take the same time for a disc of any size.
    '''
    #erosion: the places at least the radius from the edge of the mask
    core = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) > radius
    if not core.any():
        return np.zeros_like(mask)
    #dilation: the places within the radius of what was left
    near_core = cv2.distanceTransform(np.where(core, 0, 255).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) <= radius
    return np.where(near_core & (mask > 0), 255, 0).astype(np.uint8)

def detect_symbols(gray_img, img_area):
    '''
    Finds the pedigree's symbols: filled (affected) symbols from the dark parts of the image, with the lines
    removed first so that a line touching a symbol doesn't join it to the rest of the drawing, and
    unfilled (unaffected) symbols from the white space inside their outlines.

    RETURN:
    -------
    symbols (list of (bounding box (x, y, w, h), Sex, Phenotype)), and the width of the drawing's lines in pixels
    '''
    _, threshold_light = cv2.threshold(gray_img, 250, 255, cv2.THRESH_BINARY)
    _, threshold_dark = cv2.threshold(gray_img, 5, 255, cv2.THRESH_BINARY_INV)

    #lines are narrower than the symbols: opening the dark parts with a disc wider than a line removes the lines and keeps filled symbols
    line_width = stroke_width(threshold_dark)
    filled_symbols = open_with_disc(threshold_dark, 1.5*line_width)

    light_contours, hierarchy = cv2.findContours(threshold_light, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    dark_contours, _ = cv2.findContours(filled_symbols, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    #the white inside an outline is a patch of white of its own, whose edge is an outer contour, at an even depth in
    #the tree of contours. The contours at odd depths are the edges of dark shapes seen from the white around them:
    #one of these goes all the way round the drawing, and could otherwise pass for a very large symbol
    def depth(i):
        d = 0
        while hierarchy[0][i][3] != -1:
            i = hierarchy[0][i][3]
            d += 1
        return d
    light_contours = [contour for i, contour in enumerate(light_contours) if depth(i) % 2 == 0]

    symbols = []
    for phenotype, contours in ((2, dark_contours), (1, light_contours)):
        for contour in contours:
            #scaling epsilon used in polyaprox based on perimeter of the contour
            epsilon =0.02 * cv2.arcLength(contour, closed= True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            x,y,w,h = cv2.boundingRect(approx)
            bounding_area = w*h
            if bounding_area < 0.25*img_area and bounding_area > 0.0001*img_area and abs(w-h) < (min(w,h) * 0.25):
                symbols.append(((x, y, w, h), symbol_sex(contour), phenotype))
    return symbols, line_width


#-----------------------------
# LINE DETECTION
#-----------------------------
def merge_duplicate_lines(norm_cat_lines, angle_threshold= 10, distance_threshold= 50):
    '''
    Joins lines that run along one another, less than distance_threshold apart, and that overlap or meet end to end:
    Hough finds both edges of a thick line, and often finds a line in pieces. Each joined line keeps the position
    of the longer of the two. The lines are gone over again until no more can be joined, so that the pieces of a
    line are all joined whatever order they come in.
    '''
    def merge_horizontal(lines):
        merged_horizontal_lines = []
        for horz_line in lines:
            a,hy1,b,hy2 = horz_line
            for i in range(len(merged_horizontal_lines)):
                c,mhy1,d,mhy2 = merged_horizontal_lines[i]
                #sufficiently close vertically, and overlapping or touching
                if abs(mhy1 - hy1) < distance_threshold and a <= d and c <= b:
                    y = hy1 if b - a > d - c else mhy1
                    merged_horizontal_lines[i] = (min(a, c), y, max(b, d), y)
                    break
            else:
                merged_horizontal_lines.append(horz_line)
        return merged_horizontal_lines

    #vertical lines run from the bottom (the larger y) up
    def merge_vertical(lines):
        merged_vertical_lines = []
        for vert_line in lines:
            vx1,a,vx2,b = vert_line
            for j in range(len(merged_vertical_lines)):
                mvx1,c,mvx2,d = merged_vertical_lines[j]
                #sufficiently close horizontally, and overlapping or touching
                if abs(mvx1 - vx1) < distance_threshold and b <= c and d <= a:
                    x = vx1 if a - b > c - d else mvx1
                    merged_vertical_lines[j] = (x, max(a, c), x, min(b, d))
                    break
            else:
                merged_vertical_lines.append(vert_line)
        return merged_vertical_lines

    directional_merged_lines = {}
    for direction, merge in (('vertical', merge_vertical), ('horizontal', merge_horizontal)):
        lines = list(norm_cat_lines[direction])
        while True:
            merged = merge(lines)
            if len(merged) == len(lines):
                break
            lines = merged
        directional_merged_lines[direction] = merged

    return directional_merged_lines



def categorize_normalize_lines(lines, img_width, img_height, tilt_threshold = 200):
    categorized_normalized_lines = {
    'vertical': [],
    'horizontal': []
    }

    #HoughLinesP returns None when it finds no lines, and its array's shape is (n, 1, 4) in OpenCV 4 but (n, 4) in OpenCV 5
    if lines is None:
        return categorized_normalized_lines
    uncategorized = 0
    for line in np.asarray(lines).reshape(-1, 4):
        x1,y1,x2,y2 = (int(v) for v in line)
        #deleting exessively long and short duplicates/artifacts
        if (
            (abs(x2-x1) > 0.8*img_width or abs(y2-y1) > 0.8*img_height) or
            (abs(x2-x1) < 0.01*img_width and abs(y2-y1) < 0.01*img_height)
        ):
            continue
        if abs(x1 - x2) < tilt_threshold:
            if y1 < y2:
                z = y1
                y1 = y2
                y2 = z
            categorized_normalized_lines['vertical'].append((x1, y1, x2, y2))
        elif abs(y1 - y2) < tilt_threshold:
            if x1 > x2:
                z = x1
                x1 = x2
                x2 = z
            categorized_normalized_lines['horizontal'].append((x1, y1, x2, y2))
        else:
            uncategorized += 1

    if uncategorized:
        warnings.warn(f'{uncategorized} line(s) were neither horizontal nor vertical and were left out')
    return categorized_normalized_lines



def partners_at_ends(line, IndvID, IndvDataDict, distance_threshold):
    '''
    The people at the two ends of a horizontal line: at each end, whoever has a side of their symbol within
    distance_threshold of it (the closest, if several do), or None if no one does. IndvID itself is left out.
    '''
    x1, y1, x2, y2 = line
    partners = []
    for end in ((x1, y1), (x2, y2)):
        best, best_distance = None, distance_threshold
        for PartnerID in IndvDataDict.keys():
            if PartnerID == IndvID:
                continue
            px_left, py_top, pw, ph = IndvDataDict[PartnerID]['node_coords']
            #a line now stops at the edge of the margin blanked out round the symbol
            ppad = IndvDataDict[PartnerID].get('pad', 0)
            for side in ((px_left - ppad, py_top + ph/2), (px_left + pw + ppad, py_top + ph/2)):
                distance = linDist(side, end)
                if distance < best_distance:
                    best, best_distance = PartnerID, distance
        partners.append(best)
    return partners

def trackRelation(normalized_categorized_lines, IndvDataDict):
    connection_lines = []

    for IndvID in IndvDataDict.keys():
        IndvDataDict[IndvID]['PaternalID'] = 0
        IndvDataDict[IndvID]['MaternalID'] = 0
        inheritence_known = False
        #finding starting coordinate (top anchor)
        x_left, y_top, w, h = IndvDataDict[IndvID]['node_coords']
        #the symbol was blanked out with a margin round it, so the lines meeting it now stop at the edge of the margin
        pad = IndvDataDict[IndvID].get('pad', 0)
        x_mid = int(x_left + w/2)
        top_center_coord = (x_mid, y_top - pad)
        IndvDataDict[IndvID]['lat_coords'] = [(int(x_left+w+pad), int(y_top+(h/2))), (int(x_left-pad), int(y_top+(h/2)))]
        distance_threshold = h/2
        #finding if there is veritcal line close to top anchor (i.e. if inheritence is known)
        for vert_line in normalized_categorized_lines['vertical']:
            Vx1,Vy1,Vx2,Vy2 = vert_line
            if linDist(top_center_coord, (Vx1,Vy1)) < distance_threshold:
                start_coord = (Vx1,Vy1)
                current_coord = (Vx2, Vy2)
                inheritence_known = True

                break

        #checking if parental relationship was found
        #tracing back to parents if known
        if inheritence_known:
            Cx,Cy = current_coord
            endpoints = None
            #find initial horizontal
            for horz_line in normalized_categorized_lines['horizontal']:
                Hx1,Hy1,Hx2,Hy2 = horz_line
                #checking if horizontal line is at same elevation as current y and current x is between enpoints
                if abs(Cy - Hy1) < distance_threshold and (Hx1-distance_threshold < Cx and Cx < Hx2+distance_threshold):
                    endpoints = horz_line
                    break
            if endpoints is None:
                warnings.warn(f'{IndvID}: a line leaves the top of the symbol but leads to no other line, so the parents are unknown')
                continue

            #a line with someone at each end is the partners' line, which is reached straight away from an only child,
            #or from a child drawn right under the partners' line. Otherwise this is the line over a sibship, and the
            #partners' line is at the top of the line that comes down to it
            left_parent, right_parent = partners_at_ends(endpoints, IndvID, IndvDataDict, distance_threshold)
            if left_parent is None and right_parent is None:
                #find secondary vertical (if it exists)
                secondary_exists = False
                Cx1,Cy1,Cx2,Cy2 = endpoints
                for vert_line in normalized_categorized_lines['vertical']:
                    Vx1,Vy1,Vx2,Vy2 = vert_line
                    #checks that the two lines intersect in a perpendicular way
                    #adding distance threshold to Vy2 inorder to trncate the veritcal line from the top
                    #this avoid seeing downward point sibling veritcal lines and progressing along that instead of parental lines
                    if (Vy1+distance_threshold > Cy1 and Cy1 > Vy2+distance_threshold) and (Cx1-distance_threshold < Vx1 and Vx1 < Cx2+distance_threshold):
                        current_coord = (Vx2, Vy2)
                        secondary_exists = True
                        break

                #check if secondary vertical was found
                if secondary_exists:
                    Cx,Cy = current_coord
                    #find secondary horizontal
                    for horz_line in normalized_categorized_lines['horizontal']:
                        Hx1,Hy1,Hx2,Hy2 = horz_line
                        if abs(Cy - Hy1) < distance_threshold and (Hx1-distance_threshold < Cx and Cx < Hx2+distance_threshold):
                            endpoints = horz_line
                            break
                    left_parent, right_parent = partners_at_ends(endpoints, IndvID, IndvDataDict, distance_threshold)

            fx1,fy1,fx2,fy2 = endpoints
            sx, sy = start_coord
            connection_lines = connection_lines + [(sx,sy,fx1,fy1), (sx,sy,fx2,fy2)]

            #the father is the male partner, and the mother the female one, wherever they are drawn.
            #only when their sexes don't tell is the left partner taken as the father, as pedigrees are usually drawn
            father, mother = left_parent, right_parent
            left_sex = IndvDataDict[left_parent].get('Sex') if left_parent is not None else None
            right_sex = IndvDataDict[right_parent].get('Sex') if right_parent is not None else None
            if left_sex == 2 or right_sex == 1:
                father, mother = right_parent, left_parent
            if father is not None:
                IndvDataDict[IndvID]['PaternalID'] = father
            if mother is not None:
                IndvDataDict[IndvID]['MaternalID'] = mother

    return IndvDataDict, connection_lines

def pedigree_processing(FamID,
                        raw_image_dir = '.',
                        export= False,
                        output_dir = '.',
                        image_path = None,
                        upscale_factor = 10):
    '''
    Reads a pedigree image into a dataframe laid out like a PED file

    PARAMETERS:
    -----------
    FamID (string): the family's ID. Unless image_path is given, the image is raw_image_dir/<FamID>.png
    raw_image_dir (string): the folder the image is in
    export (bool): whether to write the PED file too, as output_dir/<FamID>.ped
    output_dir (string): the folder to write the PED file in
    image_path (string, optional): the image to read, in any format Pillow reads
    upscale_factor (number): how many times to enlarge the image before reading it (default = 10)

    RETURN:
    -------
    pandas.DataFrame with the columns FamilyID, IndividualID, PaternalID, MaternalID, Sex and Phenotype
    '''
    #----------------------------------------
    # ENHANCE IMAGE
    #----------------------------------------
    if image_path is None:
        image_path = f'{raw_image_dir}/{FamID}.png'
    img = upscaled_image(image_path, upscale_factor)

    #----------------------------------------
    # INDIVIDUAL ID DETECTION
    #----------------------------------------
    img_height, img_width, _ = img.shape
    img_area = img_height * img_width
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


    #the drawing is black on white, so anything nearer white than black is taken as white: this clears the grey haze
    #that JPEG compression and scanning leave around lines and text
    _, redacted_img = cv2.threshold(gray_img, 127, 255, cv2.THRESH_BINARY)

    #Tesseract reads text best when it's a few tens of pixels high, and starts to misread labels enlarged ten times,
    #so the labels are read from a copy of the image enlarged no more than three times (in grey, which it also reads
    #better), and their places are scaled up to match. The labels are scattered over the drawing rather than set
    #in lines of text, which is what Tesseract's sparse text mode (11) is for
    ocr_factor = min(upscale_factor, 3)
    ocr_img = cv2.cvtColor(upscaled_image(image_path, ocr_factor), cv2.COLOR_BGR2GRAY)
    scale = upscale_factor / ocr_factor
    TextData = pytesseract.image_to_data(ocr_img, config= '--psm 11', output_type= pytesseract.Output.DICT)
    IndvIDsDict = {}

    n_boxes = len(TextData['text'])

    #a symbol is sometimes read as a letter (a circle as O): such "text" is as tall as a symbol, much taller than the labels
    heights = [TextData['height'][i] for i in range(n_boxes) if TextData['text'][i].strip()]
    label_height = float(np.median(heights)) if heights else 0

    for i in range(n_boxes):
        IndvID = TextData['text'][i].strip()
        if IndvID and TextData['height'][i] <= 1.5*label_height:
            (x,y,w,h) = (int(scale*TextData[key][i]) for key in ('left', 'top', 'width', 'height'))
            display_coords = (x,y,w,h)
            if IndvID in IndvIDsDict:
                warnings.warn(f'The label {IndvID} appears more than once; only the last is used')
            IndvIDsDict[IndvID] = {}
            IndvIDsDict[IndvID]['label_coords'] = display_coords
            #draw a white rectangle over the ID number (with a little extra size for buffer)
            redacted_img = cv2.rectangle(redacted_img, (x-10,y-10), (x+w+20, y+h+20), (255,255,255), -1)

    if not IndvIDsDict:
        raise ValueError(f'No labels were found in {image_path}. Tesseract seldom reads labels of a single character.')

    #----------------------------------------
    # PHENOTYPE AND SEX DETECTION
    #----------------------------------------
    nodeless_img = np.copy(redacted_img)
    symbols, line_width = detect_symbols(redacted_img, img_area)

    #each symbol goes with the nearest label, and each label keeps the nearest of the symbols that chose it
    nearest = {}
    unlabelled = 0
    for (x, y, w, h), sex, phenotype in symbols:
        center_coords = ((x + w/2), y + h/2)
        label = closestLabel(marker_coords= center_coords, label_dict= IndvIDsDict)
        lx, ly, lw, lh = IndvIDsDict[label]['label_coords']
        distance = linDist(center_coords, (lx + lw/2, ly + lh/2))
        if distance > 3*max(w, h):
            unlabelled += 1
            continue
        if label in nearest:
            unlabelled += 1
            if distance > nearest[label][0]:
                continue
        nearest[label] = (distance, (x, y, w, h), sex, phenotype)
    if unlabelled:
        warnings.warn(f'{unlabelled} symbol(s) had no label of their own near them and were left out. '
                      'Tesseract often misses labels of a single character.')

    for label, (_, (x, y, w, h), sex, phenotype) in nearest.items():
        IndvIDsDict[label]['node_coords'] = (x,y,w,h)
        IndvIDsDict[label]['Phenotype'] = phenotype
        IndvIDsDict[label]['Sex'] = sex
        #blanking out the symbol, with a margin, so that only the lines between symbols are left
        #(an unfilled symbol was found by the space inside its outline, so its outline is a line's width further out)
        pad = (2 if phenotype == 1 else 1)*line_width + int(0.05*max(w, h))
        IndvIDsDict[label]['pad'] = pad
        nodeless_img = cv2.rectangle(nodeless_img, (x-pad, y-pad), (x+w+pad, y+h+pad), (255,255,255), -1)

    unmatched = [label for label in IndvIDsDict if 'node_coords' not in IndvIDsDict[label]]
    if unmatched:
        warnings.warn(f'No symbol was found for the text {", ".join(unmatched)}, which is left out')
        for label in unmatched:
            del IndvIDsDict[label]


    #----------------------------------------
    # RELATION DETECTION
    #----------------------------------------
    edges = cv2.Canny(nodeless_img, 0, 50, apertureSize= 3)
    raw_lines = cv2.HoughLinesP(edges,
                            rho=1,
                            theta= np.pi/180,
                            threshold= 50,
                            minLineLength= 5,
                            maxLineGap= img_width*0.1)

    line_img = np.copy(redacted_img)*0
    cat_norm_lines = categorize_normalize_lines(raw_lines, img_width, img_height)

    lines = merge_duplicate_lines(cat_norm_lines)
    for direction in lines.keys():
        for line in lines[direction]:
            x1, y1, x2, y2 = line
            line_img = cv2.line(line_img, (x1,y1), (x2,y2), (255,255,255), 5)

    IndvIDsDict, connection_lines = trackRelation(lines, IndvIDsDict)

    for line in connection_lines:
        x1, y1, x2, y2 = line
        line_img = cv2.line(line_img, (x1,y1), (x2,y2), (255,255,255), 5)
    for individual in IndvIDsDict.keys():
        for coord in IndvIDsDict[individual]['lat_coords']:
            line_img = cv2.circle(line_img, coord, radius=10, color=(255,255,255), thickness=-1)

    #package pedigree data into dataframe structured like PED file
    PedFileDataFields = ['PaternalID', 'MaternalID', 'Sex', 'Phenotype']
    #constructs df and subsets to PED file format-relevant fields
    PedFileDF = pd.DataFrame.from_dict(IndvIDsDict, orient= 'index')[PedFileDataFields]

    #adding individualID and FamilyID Fields (reordered to fit PED file format)
    PedFileDF.index.name = 'IndividualID'
    PedFileDF = PedFileDF.reset_index()
    PedFileDF['FamilyID'] = [FamID]*len(PedFileDF)
    PedFileDF = PedFileDF.reindex(columns= ['FamilyID', 'IndividualID']+PedFileDataFields)

    if export:
        PED_export(PedFileDF, output_dir= output_dir)

    return PedFileDF

#---------------------------------------------
# Main Pedigree Interpretation Function Test
#---------------------------------------------
if __name__ == '__main__':
    ChosenID = input('Enter A Family ID for testing: ')
    image_dir = 'data/Pedigree_Images/Raw_Images'
    FamilyPEdFileDF = pedigree_processing(FamID= ChosenID, raw_image_dir= image_dir, export= True)
    print(FamilyPEdFileDF)


