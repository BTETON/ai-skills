import sys
import os
import hashlib
import subprocess
import collections

import json
import tarfile
import io
import pickle as pkl

"""
input:
    8a610f5720b96856df771152f2a9736735695a19.story
    8a738e6dff859aca5ec507ad2ddcedab4b0bb08d.story
    8a73acec41c639c89835e3ecc89e5d3a0e730d2f.story
    ...
    8a762537bd3a4345bc6756a62db08c0435c032af.story
    
    cat 8a610f5720b96856df771152f2a9736735695a19.story
        ""
        By 
        Simon Murphy
        PUBLISHED:
        08:23 EST, 16 January 2013
        | 
            UPDATED:
        12:18 EST, 16 January 2013
        ‘There’s no fence, no sign, no warning you’re about to fall into a hole, just a few traffic cones.’
        ‘The course held up very well. There was some surface damage but actually we were very pleased with how the course endured such an extreme weather situation. There are two sections impacted because the burn burst its banks.
        ‘We have a 600-acre golf course which is sand-based and we have exceptional drainage. The pathway has collapsed into the burn.’
        
        @highlight
        The 'bullying' businessman infuriated locals when building the course
        @highlight
        Their battle featured in BBC2 documentary You’ve Been Trumped
        @highlight
        She said Trump's controversial course had drainage problems%    
        ""
output:
        0.json
        1.json
        ...
        0000.json
        
        cat 121.json
        ""
        {
           "id": "9acb288aebea0b1d9c5c49e14cd992f07e34506c",
           "article": [
               "by daily mail reporter .",
               "published : .",
               "10:40 est , 25 july 2012 .",
               "| .",
               "updated : .",
               "19:51 est , 25 july 2012 .",
               "when detectives studied his computer , they found he had set up a fictitious circle of friends on facebook -- all of whom he had used to communicate with katie , convincing her they were real .",
               "the profile pages for dan tress , cyn darwin , shane pleuon and krystal stanguard featured photographs bushby had found online .",
               "guilty : tony bushby , a teenage karate teacher , has been jailed for a minimum of 25 years after stabbing his girlfriend to death on boxing day as she babysat her niece and nephew .",
               "he was behind all the characters and they reflected his ` obsessions and interests -lrb- with -rrb- all things dark and evil ' . he even went on to blame one of his creations , dan tress , for katie 's murder .",
               "bushby denied murder but was convicted by a jury at st alban 's crown court on tuesday .",
               ......
               "miss wynter 's mother joy davis told how her world had ` crashed around ' her following the murder of her daughter .",
           ],
           "abstract": [
               "tony bushby , 19 , created fake facebook friends to trick art student catherine wynter into going out with him .",
               "he stabbed her 23 times as she babysat her niece and nephew on boxing day last year then locked them in the house with her body .",
               "mother : ` i have been robbed of a future with my daughter '"
           ],
        }         
        ""
"""
dm_single_close_quote = '\u2019' # unicode
dm_double_close_quote = '\u201d'
# acceptable ways to end a sentence
END_TOKENS = ['.', '!', '?', '...', "'", "`", '"',
              dm_single_close_quote, dm_double_close_quote, ")"]

all_train_urls = "url_lists/all_train.txt"
all_val_urls = "url_lists/all_val.txt"
all_test_urls = "url_lists/all_test.txt"

cnn_tokenized_stories_dir = "/media/webdev/store/competition/cnndm/cnn"
dm_tokenized_stories_dir = "/media/webdev/store/competition/cnndm/dm"
finished_files_dir = "/media/webdev/store/competition/cnndm"

# These are the number of .story files we expect there to be in cnn_stories_dir
# and dm_stories_dir
num_expected_cnn_stories = 92579
num_expected_dm_stories = 219506


def tokenize_stories(stories_dir, tokenized_stories_dir):
    """Maps a whole directory of .story files to a tokenized version using
       Stanford CoreNLP Tokenizer
    """
    print("Preparing to tokenize {} to {}...".format(stories_dir,
                                                     tokenized_stories_dir))
    stories = os.listdir(stories_dir)
    # make IO list file
    print("Making list of files to tokenize...")
    with open("mapping.txt", "w") as f:
        for s in stories:
            f.write(
                "{} \t {}\n".format(
                    os.path.join(stories_dir, s),
                    os.path.join(tokenized_stories_dir, s)
                )
            )
    command = ['java', 'edu.stanford.nlp.process.PTBTokenizer',
               '-ioFileList', '-preserveLines', 'mapping.txt']
    print("Tokenizing {} files in {} and saving in {}...".format(
        len(stories), stories_dir, tokenized_stories_dir))
    subprocess.call(command)
    print("Stanford CoreNLP Tokenizer has finished.")
    os.remove("mapping.txt")

    # Check that the tokenized stories directory contains the same number of
    # files as the original directory
    num_orig = len(os.listdir(stories_dir))
    num_tokenized = len(os.listdir(tokenized_stories_dir))
    if num_orig != num_tokenized:
        raise Exception(
            "The tokenized stories directory {} contains {} files, but it "
            "should contain the same number as {} (which has {} files). Was"
            " there an error during tokenization?".format(
                tokenized_stories_dir, num_tokenized, stories_dir, num_orig)
        )
    print("Successfully finished tokenizing {} to {}.\n".format(
        stories_dir, tokenized_stories_dir))


def read_story_file(text_file):
    with open(text_file, "r") as f:
        # sentences are separated by 2 newlines
        # single newlines might be image captions
        # so will be incomplete sentence
        lines = f.read().split('\n\n')
    return lines


def hashhex(s):
    """Returns a heximal formated SHA1 hash of the input string."""
    h = hashlib.sha1()
    h.update(s.encode())
    return h.hexdigest()


def get_url_hashes(url_list):
    return [hashhex(url) for url in url_list]


def fix_missing_period(line):
    """Adds a period to a line that is missing a period"""
    if "@highlight" in line:
        return line
    if line == "":
        return line
    if line[-1] in END_TOKENS:
        return line
    return line + " ."


def get_art_abs(story_file):
    """ return as list of sentences"""
    lines = read_story_file(story_file)

    # Lowercase, truncated trailing spaces, and normalize spaces
    lines = [' '.join(line.lower().strip().split()) for line in lines]

    # Put periods on the ends of lines that are missing them (this is a problem
    # in the dataset because many image captions don't end in periods;
    # consequently they end up in the body of the article as run-on sentences)
    lines = [fix_missing_period(line) for line in lines]

    # Separate out article and abstract sentences
    article_lines = []
    highlights = []
    next_is_highlight = False
    for idx, line in enumerate(lines):
        if line == "":
            continue # empty line
        elif line.startswith("@highlight"):
            next_is_highlight = True
        elif next_is_highlight:
            highlights.append(line)
        else:
            article_lines.append(line)

    return article_lines, highlights


def write_to_tar(url_file, out_file, makevocab=False):
    """Reads the tokenized .story files corresponding to the urls listed in the
       url_file and writes them to a out_file.
    """
    print("Making bin file for URLs listed in {}...".format(url_file))
    url_list = [line.strip() for line in open(url_file)]
    url_hashes = get_url_hashes(url_list)
    story_fnames = [s+".story" for s in url_hashes]
    num_stories = len(story_fnames)

    if makevocab:
        vocab_counter = collections.Counter()

    with tarfile.open(out_file, 'w') as writer:
        for idx, s in enumerate(story_fnames):
            if idx % 1000 == 0:
                print("Writing story {} of {}; {:.2f} percent done".format(
                    idx, num_stories, float(idx)*100.0/float(num_stories)))

            # Look in the tokenized story dirs to find the .story file
            # corresponding to this url
            if os.path.isfile(os.path.join(cnn_tokenized_stories_dir, s)):
                story_file = os.path.join(cnn_tokenized_stories_dir, s)
            elif os.path.isfile(os.path.join(dm_tokenized_stories_dir, s)):
                story_file = os.path.join(dm_tokenized_stories_dir, s)
            else:
                print("Error: Couldn't find tokenized story file {} in either"
                      " tokenized story directories {} and {}. Was there an"
                      " error during tokenization?".format(
                          s, cnn_tokenized_stories_dir,
                          dm_tokenized_stories_dir))
                # Check again if tokenized stories directories contain correct
                # number of files
                print("Checking that the tokenized stories directories {}"
                      " and {} contain correct number of files...".format(
                          cnn_tokenized_stories_dir, dm_tokenized_stories_dir))
                check_num_stories(cnn_tokenized_stories_dir,
                                  num_expected_cnn_stories)
                check_num_stories(dm_tokenized_stories_dir,
                                  num_expected_dm_stories)
                raise Exception(
                    "Tokenized stories directories {} and {}"
                    " contain correct number of files but story"
                    " file {} found in neither.".format(
                        cnn_tokenized_stories_dir,
                        dm_tokenized_stories_dir, s)
                )

            # Get the strings to write to .bin file
            article_sents, abstract_sents = get_art_abs(story_file)

            # Write to JSON file
            js_example = {'id': s.replace('.story', ''), 'article': article_sents, 'abstract': abstract_sents}
            js_serialized = json.dumps(js_example, indent=4).encode()
            save_file = io.BytesIO(js_serialized)
            tar_info = tarfile.TarInfo('{}/{}.json'.format(
                os.path.basename(out_file).replace('.tar', ''), idx))
            tar_info.size = len(js_serialized)
            writer.addfile(tar_info, save_file)

            # Write the vocab to file, if applicable
            if makevocab:
                art_tokens = ' '.join(article_sents).split()
                abs_tokens = ' '.join(abstract_sents).split()
                tokens = art_tokens + abs_tokens
                tokens = [t.strip() for t in tokens] # strip
                tokens = [t for t in tokens if t != ""] # remove empty
                vocab_counter.update(tokens)

    print("Finished writing file {}\n".format(out_file))

    # write vocab to file
    if makevocab:
        print("Writing vocab file...")
        with open(os.path.join(finished_files_dir, "vocab_cnt.pkl"),
                  'wb') as vocab_file:
            pkl.dump(vocab_counter, vocab_file)
        print("Finished writing vocab file")


def check_num_stories(stories_dir, num_expected):
    num_stories = len(os.listdir(stories_dir))
    if num_stories != num_expected:
        raise Exception(
            "stories directory {} contains {} files"
            " but should contain {}".format(
                stories_dir, num_stories, num_expected)
        )

"""
python make_datafiles.py /media/webdev/store/competition/cnndm/cnn_stories/stories /media/webdev/store/competition/cnndm/dm_stories/stories
cnn_stories 92580
dm_stories 219507

"""
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("USAGE: python make_datafiles.py"
              " <cnn_stories_dir> <dailymail_stories_dir>")
        sys.exit()
    cnn_stories_dir = sys.argv[1]
    dm_stories_dir = sys.argv[2]

    # Check the stories directories contain the correct number of .story files
    check_num_stories(cnn_stories_dir, num_expected_cnn_stories)
    check_num_stories(dm_stories_dir, num_expected_dm_stories)

    # Create some new directories
    if not os.path.exists(cnn_tokenized_stories_dir):
        os.makedirs(cnn_tokenized_stories_dir)
    if not os.path.exists(dm_tokenized_stories_dir):
        os.makedirs(dm_tokenized_stories_dir)
    if not os.path.exists(finished_files_dir):
        os.makedirs(finished_files_dir)

    # Run stanford tokenizer on both stories dirs,
    # outputting to tokenized stories directories
    tokenize_stories(cnn_stories_dir, cnn_tokenized_stories_dir)
    tokenize_stories(dm_stories_dir, dm_tokenized_stories_dir)

    # Read the tokenized stories, do a little postprocessing
    # then write to bin files
    write_to_tar(all_test_urls, os.path.join(finished_files_dir, "test.tar"))
    write_to_tar(all_val_urls, os.path.join(finished_files_dir, "val.tar"))
    write_to_tar(all_train_urls, os.path.join(finished_files_dir, "train.tar"),
                 makevocab=True)