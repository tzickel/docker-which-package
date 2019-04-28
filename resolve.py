# if not found packages, show files, cc -> gcc, java -> ?
# TODO add all sources.list
# TODO document you need tar
# TODO document search for provides
import subprocess
from io import BytesIO
import aptfile


debug = False


def parse_dockerfile_stream(stream, num_lines=None, fix=False):
    stream.seek(0)
    lines = []
    catline = []
    for i, line in enumerate(stream):
        lrstrip = line.rstrip()
        # Handle Dockerfile's RUN multiline support
        if lrstrip and lrstrip[-1] == b'\\':
            if not catline:
                if line.lstrip().split(b' ', 1)[0].lower() == b'run':
                    catline.append(line)
            else:
                catline.append(line)
        else:
            if catline:
                catline.append(line)
                lines.append(b''.join(catline))
                catline = []
            else:
                lines.append(line)
        if num_lines and len(lines) == num_lines:
            break
    else:
        return None
    if fix:
        line = lines[-1]
        lines = lines[:-1]
        # TODO handle SHELL FORM
        # TODO allow custom shell
        l1 = b'RUN apt-get update && apt-get install -y strace && mkdir /tmp/strace_output\n'
        l2= b'ENTRYPOINT ["strace", "-I4", "-e", "file", "-ff", "-o", "/tmp/strace_output/strace_output", "/bin/sh", "-c", "' + line.lstrip().split(b' ', 1)[1].rstrip().replace(br'"', br'\"').replace(b'\t', br'\t') + b'"]\n'
        line = b''.join([l1, l2])
        lines.append(line)
    return BytesIO(b'\n'.join(lines))


def build_with(stream, image_tag):
    p_out = subprocess.Popen('docker build -t %s -' % image_tag, shell=True, stdin=subprocess.PIPE)
    p_out.stdin.write(stream.read())
    p_out.stdin.close()
    p_out.wait()
    return p_out.returncode


def docker_get_strace_output(docker_image_id):
    # TODO check return value error
    # TODO handle finally cleanup
    # --pid=host is needed for older strace versions...
    try:
        p_out = subprocess.Popen('docker create -it --cap-add=SYS_PTRACE --pid=host %s' % docker_image_id, shell=True, stdout=subprocess.PIPE)
        docker_container_id = p_out.stdout.read().rstrip().decode()
        p_out.stdout.close()
        p_out.wait()
        p_out = subprocess.Popen('docker start -ia %s' % docker_container_id, shell=True)
        p_out.wait()
        # TODO handle processing only strace output files
        p_out = subprocess.Popen('docker cp %s:/tmp/strace_output - | tar -xvO' % docker_container_id, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        strace_output, strace_error = p_out.communicate()
        p_out.wait()
        return strace_output
    finally:
        p_out = subprocess.Popen('docker rm -f %s' % docker_container_id, shell=True)
        p_out.wait()


def docker_get_aptsources_output(docker_image_id):
    # TODO check re value error
    # TODO make this better
    p_out = subprocess.Popen('docker run -it --rm --entrypoint /bin/cat %s /etc/apt/sources.list' % docker_image_id, shell=True, stdout=subprocess.PIPE)
    debfiles = p_out.stdout.read()
    p_out.stdout.close()
    p_out.wait()
    return debfiles


def parse_strace_output(strace_output):
    fnames = []
    for line in strace_output.split(b'\n'):
        if debug:
            print(line)
        if b'=' not in line:
            continue
        data = line.rsplit(b' = ', 1)
        if len(data) >= 2 and b'ENOENT' in data[1]:
            # TODO make this less flaky
            fname = data[0].split(b'"', 1)[1].split(b'", ', 1)[0]
            if fname.startswith(b'/usr/local') or not fname.startswith(b'/') or fname.startswith(b'/tmp'):
                continue
            fnames.append(fname)
    return fnames


def build_till_next_error(stream, image_tag):
    i = 1
    while True:
        s = parse_dockerfile_stream(stream, i)
        if s is None:
            return None
        returncode = build_with(s, image_tag)
        if returncode != 0:
            build_with(parse_dockerfile_stream(stream, i, True), image_tag)
            return docker_get_strace_output(image_tag)
        i += 1


def find_next_packages(input_stream, image_name):
    strace_output = build_till_next_error(input_context, image_name)
    if strace_output is None:
#        print('build finished without errors')
        return
    if debug:
        print(strace_output)
    missing_files = parse_strace_output(strace_output)
    if debug:
        print(set(missing_files))
    sources = docker_get_aptsources_output(image_name)
    if debug:
        print(sources)
    s = BytesIO(sources)
    output = BytesIO()
    aptfile.update(s, output)
    output.seek(0)
    missing_packages, conflicting_packages = aptfile.find_packages(missing_files, output)
    return missing_packages, conflicting_packages, missing_files


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        sys.stderr.write('Usage: %s <docker filename> <temporary build docker image name>\n\n' % sys.argv[0])
        sys.stderr.write('Tries to docker build the docker filename and figure out missing packages.\n\n')
        sys.exit(1)
    dockerfilename = sys.argv[1]
    image_name = sys.argv[2]
    #dockerfilename = 'Dockerfile'
    #image_name = 'build_tmp'
    try:
        input_context = open(dockerfilename, 'rb')
        result = find_next_packages(input_context, image_name)
        if not result:
            print('Finished building without errors')
            sys.exit(0)
        missing_packages, conflicting_packages, missing_files = result
        if conflicting_packages:
            print('The following packages are conflicting, decide which one of them:')
            for conflicting_package in conflicting_packages:
                print(conflicting_package)
        if not missing_packages:
            print('Could not find any missing packages, this might mean that the missing packages is an alternative one, such as cc or java or a virtual one')
            print('Printing missing files:')
            for missing_file in missing_files:
                print(missing_file)
        print('Missing packages:')
        for missing_package in missing_packages:
            print(missing_package)
    finally:
        p_out = subprocess.Popen('docker rmi -f %s' % image_name, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p_out.communicate()
        p_out.wait()
