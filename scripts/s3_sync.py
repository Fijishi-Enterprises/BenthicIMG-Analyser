# Sync files from a local directory to an S3 bucket.
#
# Non-recursive (doesn't check subfolders).
# Not a true sync; only transfers if doesn't exist in dest OR
# exists with a different size. Doesn't compare date/time or checksum.
#
# Requires AWS CLI, so must be run from an EC2 instance.
# If the local directory is not on AWS but is on an SSH-able machine,
# use sshfs to mount that directory on an EC2 instance.
#
# This script simply walks through the directory and uses "aws s3 cp" to
# copy individual files.
# It uses "aws s3 ls" to check if files already exist in the S3 destination.
#
# Here's how to specify an S3 filepath format for the destination argument:
# s3://my-bucket-name/path/to/file
#
# To work on a subset of the files in a folder, use --filter. For example,
# all files starting with 00: --filter "00.*"
#
# To kill the transfer, do Ctrl+Z, use "ps aux" to find the main process
# ("sudo python s3_sync.py ..." if run with sudo), do "kill <pid>" on the
# process, then "fg" to finish the kill. Ctrl+C will be fruitless, as it only
# kills the current file transfer.
#
#
# Why do we need this script? Well, normally we would be able to use
# the "aws s3 sync" command to do the sync:
# http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonS3.html
#
# However, aws s3 sync seems to hang when working with large directories.
# Something like this, except it doesn't transfer anything
# at all for our data-images directory:
# https://github.com/aws/aws-cli/issues/1775

import argparse
import datetime
import os
import posixpath
import re
import subprocess


if __name__ == '__main__':

    # Parse command line arguments.
    arg_parser = argparse.ArgumentParser(
        description=""
    )
    arg_parser.add_argument(
        'src_dir',
        type=str,
        help=(
            "Source directory."
        ),
    )
    arg_parser.add_argument(
        'dest_dir',
        type=str,
        help=(
            "Destination directory."
        ),
    )
    arg_parser.add_argument(
        '--filter',
        dest='filepath_filter',
        type=str,
        help=(
            "Filepath filter pattern; copy only the matching files."
        ),
    )
    args = arg_parser.parse_args()
    
    start_time = datetime.datetime.now()
    
    print("Getting destination directory listing. Could take a few minutes...")
    dest_dir = args.dest_dir
    if not dest_dir.endswith('/'):
        # Must end in a slash for 'aws s3 ls' to give the contents of
        # the directory.
        dest_dir = dest_dir + '/'
        
    dest_dir_listing = subprocess.check_output(
        ['aws', 's3', 'ls', dest_dir])
    
    print("Processing destination directory listing...")
    # This is one part of the code that's non-recursive, i.e. it won't
    # look in directories. It's possible to implement that, if we wanted to.
    # It's also possible to get dates/times of files here.
    dest_dir_files = dict()
    for line in dest_dir_listing.splitlines():
        try:
            date_str, time_str, size_str, filename = line.split()
        except ValueError as e:
            # First entry has no filename, and directory entries are
            # missing tokens. We'll skip these entries.
            #
            # We'll just be lazy here and not check to see if there are other
            # unexpected cases. Even if there are other cases,
            # that just means we might needlessly re-copy a file over.
            # Not the end of the world, and detectable when it happens.
            continue
        
        dest_dir_files[filename] = dict(size=int(size_str))
    
    print("Filter regex: " + args.filepath_filter)
    filepath_filter_regex = re.compile(args.filepath_filter)
    copied_file_count = 0
    existing_skip_file_count = 0
    nonmatch_skip_file_count = 0
    total_file_count = 0
    
    print(
        "Getting source directory listing. Could take a few minutes."
        " If it takes longer and you're accessing the source via sshfs:"
        " Ctrl+C, do an ls of a directory in the sshfs to make sure"
        " it's awake, then try again.")
    root_src_dir = args.src_dir
    rel_dir = ''
    src_dir = os.path.join(root_src_dir, rel_dir)
    src_dir_listing = subprocess.check_output(
        ['sudo', 'ls', '-la', src_dir])
    
    print("Processing source directory listing...")
    for line in src_dir_listing.splitlines():
        try:
            perms, _, _, _, src_size_str, _, _, _, filename = line.split()
        except ValueError as e:
            if line.startswith('total'):
                # First line of ls output, showing the total number of
                # file system blocks used by the listed files.
                continue
            else:
                # Unknown error.
                print("Error on this line: " + line)
                raise e
        
        if perms[0] == 'd':
            # Directory; skip
            continue
            
        total_file_count += 1
        
        rel_filepath = posixpath.join(rel_dir, filename)
        if filepath_filter_regex:
            if not re.match(filepath_filter_regex, rel_filepath):
                nonmatch_skip_file_count += 1
                print(
                    ("{rel_filepath} - Skipped, doesn't match filter regex"
                    " ({nonmatch} not matched / {total} total)").format(
                        rel_filepath=rel_filepath,
                        nonmatch=nonmatch_skip_file_count,
                        total=total_file_count,
                    )
                )
                continue
                
        src_size = int(src_size_str)
        src_filepath = os.path.join(root_src_dir, rel_filepath)
        
        # Check for existence.
        if rel_filepath in dest_dir_files:
            # Check the filesize, in case a previous transfer
            # was interrupted.
            dest_size = dest_dir_files[rel_filepath]['size']
            if dest_size == src_size:
                existing_skip_file_count += 1
                print(
                    ("{rel_filepath} - Skipped, already exists in dest"
                    " ({existing} existing / {total} total)").format(
                        rel_filepath=rel_filepath,
                        existing=existing_skip_file_count,
                        total=total_file_count,
                    )
                )
                continue
            else:
                print(
                    ("File exists, but different size"
                    " ({size1} vs. {size2}). Copying...").format(
                        size1=src_size, size2=dest_size))
        
        dest_filepath = posixpath.join(args.dest_dir, rel_filepath)
        
        subprocess.call(['aws', 's3', 'cp', src_filepath, dest_filepath])
        copied_file_count += 1
        print(
            ("{rel_filepath} - Copied to dest"
            " ({copied} copied / {total} total)").format(
                rel_filepath=rel_filepath,
                copied=copied_file_count,
                total=total_file_count,
            )
        )
            
    end_time = datetime.datetime.now()
    time_taken_str = str(end_time - start_time)
    summary = (
        "Summary:"
        "\n{copied} copied"
        "\n{existing} skipped because already exists in dest with same size"
        "\n{nonmatch} skipped because doesn't match filter regex"
        "\n{total} total"
        "\n{time_taken} elapsed").format(
            copied=copied_file_count,
            existing=existing_skip_file_count,
            nonmatch=nonmatch_skip_file_count,
            total=total_file_count,
            time_taken=time_taken_str,
        )
    print(summary)
    with open('sync_summary.txt', 'w') as f:
        f.write(summary)