
import numpy as np
import lifelib as ll
import os
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.animation as animation
import matplotlib.collections as mcoll
from itertools import permutations
import random
import pickle
import cellpylib as cpl
from hashlife.hashlife import construct, advance, expand, print_node, centre
from tqdm import tqdm
import time

catagolue_url = "https://assemblyca.github.io/static"


def step(x, rule_b):
    """Compute a single stet of an elementary cellular
    automaton."""
    # The columns contains the L, C, R values
    # of all cells.
    u = np.array([[4], [2], [1]])
    y = np.vstack((np.roll(x, 1), x,
                   np.roll(x, -1))).astype(np.int8)
    # We get the LCR pattern numbers between 0 and 7.
    z = np.sum(y * u, axis=0).astype(np.int8)
    # We get the patterns given by the rule.
    return rule_b[7 - z]


def generate(rule, initial, size=100, steps=100):
    """Simulate an elementary cellular automaton given
    its rule (number between 0 and 255)."""
    # Compute the binary representation of the rule.
    rule_b = np.array(
        [int(_) for _ in np.binary_repr(rule, 8)],
        dtype=np.int8)
    x = np.zeros((steps, size), dtype=np.int8)
    # Random initial state.
    x[0, :] = initial
    # Apply the step function iteratively.
    for i in range(steps - 1):
        x[i + 1, :] = step(x[i, :], rule_b)
    return x


def file_to_string(file_path):
    "From file get string, mostly to get large rles"
    try:
        with open(file_path, 'r') as file:
            text_string = file.read()
        return text_string
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return ""

# Modified from life_lib for plotting rules


def regstring(x):

    if isinstance(x, str):
        return x
    else:
        return x.decode('utf-8')


def prepare_110_glider():

    rep = 6
    init = np.array([0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 1, 1, 1, 1])
    right_one = np.array([0, 0, 0, 1, 0, 1, 1, 0, 0, 0,
                         1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1])
    temp = np.copy(init)
    for i in range(rep):
        temp = np.concatenate((temp, init), axis=0)

    temp = np.concatenate(
        (temp[5:], init, init, right_one, temp, init[:5]), axis=0)

    return temp


def write_rle_mod(pattern, rule, filename, header=None, footer=None, comments=None, file_format='rle', save_comments=True):

    filename = os.path.abspath(filename)

    if header is None:
        header = ''

    if footer is None:
        footer = ''

    if save_comments:
        if comments is None:
            comments = pattern.comments
        if hasattr(comments, 'splitlines'):
            comments = comments.splitlines()
        comments = [(x if x.startswith('#C ') else ('#C ' + x))
                    for x in comments]
        header += ''.join([('%s\n' % x) for x in comments])

    llc = 'SavePatternRLE' if (
        file_format[-3:].lower() == 'rle') else 'SavePatternMC'

    code = pattern.rle_string()
    code_mode = re.sub(
        'rule = .*?\n', 'rule = {}\n'.format(rule), code, flags=re.DOTALL)
    # print(code_mode)
    content = header+code_mode+footer
    f = open(filename, "w+")
    f.write(content)
    f.close()
    # pattern.lifelib(llc, pattern.ptr, filename, header, footer)


def viewer_mod(pattern, filename=None, width=480, height=480, base64=True, lv_config='#C [[ THEME 6 GRID GRIDMAJOR 0 ]]', autoremove=True, edit=True, rule=None):

    if rule is None:
        rule = pattern.getrule()

    if filename is None:
        filename = pattern.session.newfloat('viewer') + '.html'

    header = '<html><head><meta name="LifeViewer" content="rle code"></head><body>'
    header += '<div class="rle"><div style="display:none;"><code id="code2">\n'
    footer = '#C [[ WIDTH %d HEIGHT %d ]]\n' % (width, height)
    footer += '</code></div>\n<canvas width="%d" height="%d" style="margin-left:1px;"></canvas></div>\n' % (
        width+16, height+16)
    footer += "<script type='text/javascript' src='%s/js/lv-plugin.js'></script>\n" % catagolue_url

    if edit:
        # Generate a unique identifier for the IFrame, so that the Jupyter
        # notebook knows which LifeViewer has been updated with Ctrl+S.
        from uuid import uuid4
        saveid = str(uuid4())

        # Track when the (invisible!) RLE element is changed, and signal
        # those changes in a message from the IFrame to the notebook. We
        # can catch these messages in the notebook itself.
        footer += '''<script>
var targetNode = document.getElementById('code2');
var config = { attributes: true, childList: true, subtree: true };
var callback = function(mutationsList, observer) {
console.log("DOM mutated.");
parent.postMessage({ rle: targetNode.innerHTML, uuid: "%s" }, "*");
};
var observer = new MutationObserver(callback);
observer.observe(targetNode, config);
</script>''' % saveid

        # Register this pattern in the registry:
        ll.registry.register_pattern_callback(saveid, pattern)

    footer += '</body></html>\n'

    write_rle_mod(pattern, rule, filename, header, lv_config + '\n' + footer)

    if base64:

        from base64 import b64encode

        with open(filename, 'rb') as f:
            b64html = regstring(b64encode(f.read()))
        source = 'data:text/html;base64,%s' % b64html

        if autoremove:
            try:
                os.remove(filename)
            except OSError:
                pass

    else:
        source = filename

    from IPython.display import IFrame

    return IFrame(source, width=width+32, height=height+32)


def plot3d_animate(ca, title='evolved', face_color='#1f77b4', edge_color='gray', shade=False, show_grid=False, show_margin=True, scale=0.6, dpi=80, interval=100, save=False, autoscale=False, show=True, show_axis=False):
    """
    Animate the given 3D cellular automaton.
    The `show_margin` argument controls whether or not a margin is displayed in the resulting plot. When `show_margin` is set to `False`, then the plot takes up the entirety of the window. The `scale` argument is only used when the `show_margins` argument is `False`. It controls the resulting scale (i.e. relative size) of the image when there are no margins.
    The `dpi` argument represents the dots per inch of the animation when it is saved. There will be no visible effect of the `dpi` argument if the animation is not saved (i.e. when `save` is `False`).

    :param ca:  the 3D cellular automaton to animate

    :param title: the title to place on the plot (default is "")

    :param face_color: HTML color code for voxel faces (default '#1f77b4') (supports alpha channel, e.g.: '#1f77b430')

    :param edge_color: HTML color code for voxel edges (default 'gray')

    :param shade: whether to shade the voxels (default False)

    :param colormap: the color map to use (default is "Greys")

    :param show_grid: whether to display a grid (default is False)

    :param show_margin: whether to display the margin (default is True)

    :param scale: the scale of the figure (default is 0.6)

    :param dpi: the dots per inch of the image (default is 80)

    :param interval: the delay between frames in milliseconds (default is 50)

    :param save: whether to save the animation to a local file (default is False)

    :param save_path: file path to save animation to (default is 'evolved.gif')

    :param autoscale: whether to autoscale the images in the animation; this should be set to True if the first frame has a uniform value (e.g. all zeroes) (default is False)

    :param show: show the plot (default is True)

    :param show_axis: show the axis (default is False)

    :param imshow_kwargs: keyword arguments for the Matplotlib `imshow` function

    :return: the animation
    """

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    if not show_margin:
        fig.subplots_adjust(left=0, bottom=0, right=1,
                            top=1, wspace=0, hspace=0)

    if not show_axis:
        ax.xaxis.set_major_locator(ticker.NullLocator())
        ax.yaxis.set_major_locator(ticker.NullLocator())
        ax.zaxis.set_major_locator(ticker.NullLocator())
    else:
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")

    ax.set_title(title)

    ax.grid(show_grid)
    ax.voxels(ca[0], facecolors=face_color, edgecolors=edge_color, shade=shade)

    def update(i, ca):
        ax.clear()

        if not show_axis:
            ax.xaxis.set_major_locator(ticker.NullLocator())
            ax.yaxis.set_major_locator(ticker.NullLocator())
            ax.zaxis.set_major_locator(ticker.NullLocator())
        else:
            ax.set_xlabel("x")
            ax.set_ylabel("y")
            ax.set_zlabel("z")

        ax.set_title(title)

        ax.grid(show_grid)
        vox = ax.voxels(ca[i], facecolors=face_color,
                        edgecolors=edge_color, shade=shade)

    ani = animation.FuncAnimation(fig, update, fargs=(
        ca,), frames=len(ca), interval=interval, blit=False)

    if save:
        ani.save(f"{title}.gif", dpi=dpi, writer="imagemagick")

    if show:
        plt.show()

    plt.close(fig)

    return ani


def block_rule(rule, n, t):
    if n == tuple(rule[0][0]):
        return tuple(rule[0][1])
    elif n == tuple(rule[1][0]):
        return tuple(rule[1][1])
    elif n == tuple(rule[2][0]):
        return tuple(rule[2][1])
    elif n == tuple(rule[3][0]):
        return tuple(rule[3][1])
    elif n == tuple(rule[3][0][::-1]):
        return tuple(rule[3][1][::-1])
    elif n == tuple(rule[4][0]):
        return tuple(rule[4][1])
    elif n == tuple(rule[4][0][::-1]):
        return tuple(rule[4][1][::-1])
    elif n == tuple(rule[5][0]):
        return tuple(rule[5][1])
    elif n == tuple(rule[5][0][::-1]):
        return tuple(rule[5][1][::-1])


def set_rule(regla):

    rules = get_all_block_rules()

    return rules[regla]


def get_all_block_rules():

    p = {}
    p['00'] = [0, 0]
    p['11'] = [1, 1]
    p['22'] = [2, 2]
    p['01'] = [0, 1]
    p['02'] = [0, 2]
    p['12'] = [1, 2]
    p['10'] = [1, 0]
    p['20'] = [2, 0]
    p['21'] = [2, 1]

    power = 3
    lista = []
    for i in range(2**power):
        lista.append(list(format(i, '#05b')[2:]))

    lista_a = ['01', '02', '12']
    lista_b = ['10', '20', '21']
    lista_block = []
    for case in lista:
        block = []
        for i, boolean in enumerate(case):
            if boolean == '0':
                block.append(lista_a[i])
            if boolean == '1':
                block.append(lista_b[i])
        lista_block.append(block)

    # Get all permutations of [1, 2, 3]
    lista_fixed = ['01', '02', '12']

    # Print the obtained permutations
    unique_combinations = []
    for lista in lista_block:
        perm = permutations(lista_fixed)
        for i in list(perm):
            zipped = zip(i, lista)
            unique_combinations.append(list(zipped))

    to_be_combined = [[('11', '11'), ('22', '22')], [
        ('11', '22'), ('22', '11')]]
    zero = [('00', '00')]

    temp = [[], [], []]
    unique_combinations_corrected = []
    for unique in unique_combinations:
        for pair in unique:
            if pair[0] == '01':
                temp[0] = pair
            if pair[0] == '02':
                temp[1] = pair
            if pair[0] == '12':
                temp[2] = pair
        final = temp.copy()
        unique_combinations_corrected.append(final)

    unique_combinations_final = []
    for add in to_be_combined:
        for unique in unique_combinations_corrected:
            unique_combinations_final.append(
                [[p[pair[0]], p[pair[1]]] for pair in zero+add + unique])

    return unique_combinations_final


def game_of_life_rule_3d(neighbourhood, c, t):
    """
    Conway's Game of Life, in 3D.

    :param neighbourhood: the current cell's neighbourhood

    :param c: the index of the current cell

    :param t: the current timestep

    :return: the state of the current cell at the next timestep
    """

    center_cell = neighbourhood[1][1][1]
    total = neighbourhood.sum(-1).sum(-1).sum() - center_cell

    # Rule 1: Any live cell with <5 or >7 neighbours dies.
    if (total < 5 or total > 7) and center_cell == 1:
        return 0

    # Rule 2: Any dead cell with 6 neighbours becomes a live cell.
    elif total == 6 and center_cell == 0:
        return 1

    # Rule 3: Any other cell stays in same state
    else:
        return center_cell


def max_hash_ass_formula(k, n,base=2):
    suma = np.array([base**(2**i) for i in range(1, n-k+1)])
    return 2**k - 1 + np.sum(suma)


def find_k(n,base=2):
    k = 0
    for j in range(1, n):
        if 2**(n-j-1)-base**(2**(j)) < 0:
            return n-j+1
    return k


def max_hash_ass(n,base=2):
    k = find_k(n,base)
    return max_hash_ass_formula(k, n,base)


def entropy_trinary(string):
    ratio0 = string.count("0")/len(string)
    ratio1 = string.count("1")/len(string)
    ratio2 = string.count("2")/len(string)
    entropy = -1*ratio0*np.log2(ratio0) - 1*ratio1 * \
        np.log2(ratio1) - 1*ratio2*np.log2(ratio2)
    if np.isnan(entropy):
        return 0.0
    return entropy


def entropy(string):
    ratio0 = string.count("0")/len(string)
    ratio1 = string.count("1")/len(string)
    return -1*ratio0*np.log2(ratio0) - 1*ratio1*np.log2(ratio1)


def p2_len(string):
    if abs(np.log2(len(string))-int(np.log2(len(string)))) > 1e-8:
        n = int(np.log2(len(string)))+1
    else:
        n = int(np.log2(len(string)))
    return n


def join_trees(tree_a, tree_b):
    trees = [tree_a[0], tree_b[0]]
    trees_length = [len(t) for t in trees]
    min_ind = trees_length.index(min(trees_length))
    min_tree = trees[min_ind]
    max_tree = trees[min_ind-1]
    merge_tree = []
    ma = 0
    for i, layer in enumerate(max_tree):
        if i < len(min_tree):
            merge_tree.append(np.unique(np.concatenate(
                (trees[0][-1-i], trees[1][-1-i]), axis=0), axis=0))
        else:
            merge_tree.append(max_tree[-1-i])
        if i > 0:
            ma = ma + np.shape(merge_tree[-1])[0]

    merge_tree.append(
        np.array([trees[0][0][0] + trees[1][0][0]]))
    return merge_tree[::-1], ma+1


def hash_assembly(string):
    n = p2_len(string)
    size = 2**n - len(string)
    if size == 0:
        return hash_assembly_power(string)
    binary = "{0:b}".format(len(string))
    indexes = [0]
    for i, char in enumerate(binary):
        if int(char):
            index = 2**(len(binary) - i - 1) + indexes[-1]
            indexes.append(index)
    ma_hash = []
    for i, _ in enumerate(indexes[1:]):
        temp_array = string[indexes[i]:indexes[i+1]]
        cur_ma = hash_assembly_power(temp_array)
        if i == 0:
            ma_hash = cur_ma
        else:
            ma_hash = join_trees(ma_hash, cur_ma)

    return ma_hash


def hash_assembly_power(string):
    n = p2_len(string)
    size = 2**n - len(string)
    layers = []
    for i in range(n+1):
        if i == 0:
            layers.append(np.array([string]))
            continue
        layer = []
        for j, substring in enumerate(layers[i-1]):
            layer.append(substring[0:int(len(substring)/2)])
            layer.append(substring[int(len(substring)/2):])
        layers.append(np.unique(layer, axis=0))
    ma = 0
    for layer in layers[:-1]:
        ma = ma + np.shape(layer)[0]
    return layers, ma


def hash_assembly_weight(string):
    new_layers, _ = hash_assembly(string)
    ma = 0
    for layer in new_layers[:-1]:
        ma = ma + np.shape(layer)[0]*np.shape(layer)[1]
    return new_layers, ma


def hash_assembly_scale(string, layer):
    new_layers, _ = hash_assembly(string)
    ma = 0
    for layer in new_layers[layer:-1]:
        ma = ma + np.shape(layer)[0]
    return new_layers, ma


def runif_in_simplex(n):
    ''' Return uniformly random vector in the n-simplex '''

    k = np.random.exponential(scale=1.0, size=n)
    return k / sum(k)


def random_string(prob, n):
    string = []
    for i in range(n):
        ra = random.uniform(0, 1)
        if ra < prob[0]:
            string.append(0)
        elif ra < prob[0]+prob[1]:
            string.append(1)
        else:
            string.append(2)
    return string


def transf_array(array):
    join = ""
    for i in array:
        join = join + str(i)
    return join


def max_hash_assembly(n):

    if n < 2:
        raise ValueError("the string length should be more than 2")

    d_2 = np.load("benchmark_data/max_ma.npy")

    return d_2[n]


def min_hash_assembly(n):

    if n < 2:
        raise ValueError("the string length should be more than 2")

    binary = "{0:b}".format(n)
    M = binary.count('1')
    N_1 = len(binary)

    return N_1 + M - 2


def norm_hash_assembly(string):

    _, hash_ass = hash_assembly(string)
    max_hash_ass = max_hash_assembly(len(string))
    min_hash_ass = min_hash_assembly(len(string))

    return (hash_ass - min_hash_ass)/(max_hash_ass - min_hash_ass)


def plot_1d_pattern(pattern):

    fig = plt.figure()
    ax = fig.gca()
    y_lim, x_lim = np.shape(pattern)
    ax.set_xticks(np.arange(-0.5, x_lim-0.5, 1))
    ax.set_yticks(np.arange(-0.5, y_lim-0.5, 1))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    plt.imshow(np.array(1-pattern), cmap='Greys', interpolation='none')
    plt.grid()
    plt.show()

    return None


def _add_grid_lines(ca, ax, show_grid):
    """
    Adds grid lines to the plot.

    :param ca: the 2D cellular automaton to plot

    :param ax: the Matplotlib axis object

    :param show_grid: whether to display the grid lines

    :return: the grid object
    """
    grid_linewidth = 0.0
    if show_grid:
        plt.xticks(np.arange(-.5, len(ca[0][0]), 1), "")
        plt.yticks(np.arange(-.5, len(ca[0]), 1), "")
        plt.tick_params(axis='both', which='both', length=0)
        grid_linewidth = 0.5
    vertical = np.arange(-.5, len(ca[0][0]), 1)
    horizontal = np.arange(-.5, len(ca[0]), 1)
    lines = ([[(x, y) for y in (-.5, horizontal[-1])] for x in vertical] +
             [[(x, y) for x in (-.5, vertical[-1])] for y in horizontal])
    grid = mcoll.LineCollection(
        lines, linestyles='-', linewidths=grid_linewidth, color='grey')
    ax.add_collection(grid)

    return grid


def plot2d_animate(ca, title='', *, colormap='Greys', show_grid=False, show_margin=True, scale=0.6, dpi=80,
                   interval=50, save=False, autoscale=False, show=True, **imshow_kwargs):
    """
    Animate the given 2D cellular automaton.

    The `show_margin` argument controls whether or not a margin is displayed in the resulting plot. When `show_margin`
    is set to `False`, then the plot takes up the entirety of the window. The `scale` argument is only used when the
    `show_margins` argument is `False`. It controls the resulting scale (i.e. relative size) of the image when there
    are no margins.

    The `dpi` argument represents the dots per inch of the animation when it is saved. There will be no visible effect
    of the `dpi` argument if the animation is not saved (i.e. when `save` is `False`).

    :param ca:  the 2D cellular automaton to animate

    :param title: the title to place on the plot (default is "")

    :param colormap: the color map to use (default is "Greys")

    :param show_grid: whether to display a grid (default is False)

    :param show_margin: whether to display the margin (default is True)

    :param scale: the scale of the figure (default is 0.6)

    :param dpi: the dots per inch of the image (default is 80)

    :param interval: the delay between frames in milliseconds (default is 50)

    :param save: whether to save the animation to a local file (default is False)

    :param autoscale: whether to autoscale the images in the animation; this should be set to True if the first
                      frame has a uniform value (e.g. all zeroes) (default is False)

    :param show: show the plot (default is True)

    :param imshow_kwargs: keyword arguments for the Matplotlib `imshow` function

    :return: the animation
    """
    cmap = plt.get_cmap(colormap)
    fig, ax = plt.subplots()
    plt.title(title)
    if not show_margin:
        fig.subplots_adjust(left=0, bottom=0, right=1,
                            top=1, wspace=0, hspace=0)

    grid = _add_grid_lines(ca, ax, show_grid)

    im = plt.imshow(ca[0], animated=True, cmap=cmap, **imshow_kwargs)
    if not show_margin:
        baseheight, basewidth = im.get_size()
        fig.set_size_inches(basewidth*scale, baseheight*scale, forward=True)

    i = {'index': 0}

    def updatefig(*args):
        i['index'] += 1
        if i['index'] == len(ca):
            i['index'] = 0
        im.set_array(ca[i['index']])
        if autoscale:
            im.autoscale()
        return im, grid
    ani = animation.FuncAnimation(
        fig, updatefig, interval=interval, blit=True, save_count=len(ca))
    if save:
        ani.save('evolved.gif', dpi=dpi, writer="imagemagick")
    if show:
        plt.show()

    plt.close(fig)
    return ani


def assembly_distance(string1, string2):

    tree1 = hash_assembly(string1)[0]
    tree2 = hash_assembly(string2)[0]

    return assembly_distance_tree(tree1, tree2)


def assembly_distance_tree(tree1, tree2):
    inter = []
    for i, _ in enumerate(tree1):
        aset = set([x for x in tree1[i]])
        bset = set([x for x in tree2[i]])
        inter.append(np.array([x for x in aset & bset]))

    total = sum([np.shape(i)[0] for i in inter])-np.shape(inter[-1])[0]
    return inter, total


def unique_elements(tree):
    unique_elements = []
    for layer in tree:
        unique_elements = unique_elements + layer.tolist()

    return set(unique_elements)


def memory_tree(unique_a, tree):

    unique_b = unique_elements(tree)
    return unique_a.union(unique_b)


def memory(unique_a, string):

    tree = hash_assembly(string)[0]

    return memory_tree(unique_a, tree)


def maximal_string(n):

    max_strings_4_v5 = pickle.load(open("benchmark_data/outfile.pkl", "rb"))
    binary = "{0:b}".format(n)
    string_binary = ""
    for j, val in enumerate(binary[::-1]):
        if val == "1":
            string_binary = max_strings_4_v5[::-1][j] + string_binary

    return string_binary

# Helper function to compute mutual-inf row


def calculate_mutual_row(x, data_row):  # data row is a tuple of (index, text)
    i = data_row[0]  # index of the data and data_row[1] is the text data
    # calcs the row of NCD values for the given data sample
    compare = "".join([str(k) for k in data_row[1]])
    row = [cpl.mutual_information(compare, "".join(
        [str(k) for k in x[j]])) for j in range(len(x))]
    return i, row  # return index and row's mutual-inf values

# Helper function to compute hash-ass row


def calculate_ass_row(x, data_row):  # data row is a tuple of (index, text)
    i = data_row[0]  # index of the data and data_row[1] is the text data
    # calcs the row of NCD values for the given data sample
    compare = "".join([str(k) for k in data_row[1]])
    row = [assembly_distance(compare, "".join([str(k) for k in x[j]]))[
        1] for j in range(len(x))]
    return i, row  # return index and row's hash-ass values


def hash_list_reverse(node, level=0):
    """Turn a quadtree a list of (x,y,gray) triples 
    in the rectangle (x,y) -> (clip[0], clip[1]) (if clip is not-None).    
    If `level` is given, quadtree elements at the given level are given 
    as a grayscale level 0.0->1.0,  "zooming out" the display.
    """

    if node.n == 0:  # quick zero check
        return []
    size = 2 ** node.k
    if node.k == level:
        # base case: return the gray level of this node

        return [node.hash]
    else:
        # return all points contained inside this node

        return list(set([node.hash] +
                        hash_list_reverse(node.a,  level)
                        + hash_list_reverse(node.b, level)
                        + hash_list_reverse(node.c,  level)
                        + hash_list_reverse(node.d,  level)
                        ))


def hash_list_ordered(node, level=0):

    return list(set(hash_list_reverse(node)) - set(hash_list_reverse(node, level)))


def add_hash_tree(dict, hash_list):
    for item in hash_list:
        if item in dict:
            dict[item] = dict[item] + 1
        else:
            dict[item] = 1
    return dict


def measure_hash_tree(dict):

    return sum(dict.values())


def repeat(func, n, x):
    for _ in range(n):
        x = func(x)
    return x


def assembly_k_t(timescale, k, node, timeout=1e10):
    tic = time.perf_counter()
    normalized_node = repeat(centre, k - node.k, node)
    hash_tree = hash_list_ordered(normalized_node, k)
    dict_hashtree = add_hash_tree({}, hash_tree)
    assembly_n = [measure_hash_tree(dict_hashtree)]
    for n in tqdm(range(2, timescale), desc=" inner loop", position=1, leave=False):
        node = advance(node, 1)  # forward 30 generations
        normalized_node = repeat(centre, k - node.k, node)
        dict_hashtree = add_hash_tree(
            dict_hashtree, hash_list_ordered(normalized_node, k)
        )
        assembly_n.append(measure_hash_tree(dict_hashtree) * (1 / n))
        toc = time.perf_counter()
        if (toc - tic) > timeout:
            return assembly_n

    return assembly_n
