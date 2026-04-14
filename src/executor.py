import subprocess

class CodeExecutor:
    def __init__(self):
        self.bash_code_path = None
        self.bash_code_path_execute = None
        self.code_prefix = ['source "$(conda info --base)/etc/profile.d/mamba.sh"', 'mamba activate MOA']
        self.code_postfix = []

    def execute(self, bash_code_path):
        self.bash_code_path = bash_code_path  # 在execute方法中修改实例属性值self.bash_code_path
        
        with open(self.bash_code_path, 'r') as object:
            bash_content = object.read()

        self.bash_code_path_execute = self.bash_code_path + '.execute.sh'  # 创建新的execute.sh，在execute.sh上执行

        # 打开新生成的 Bash 文件以供写入
        with open(self.bash_code_path_execute, 'w') as output_file:
            for code in self.code_prefix:
                output_file.write(code + '\n')
            # 写入原始内容
            output_file.write(bash_content)
            output_file.write('\n')  # 确保在新行开始
            for code in self.code_postfix:
                output_file.write(code + '\n')

        # 使用 subprocess 执行 Bash 文件，将输出捕获到一个字符串中
        process = subprocess.Popen(['bash', '-i', '-e', self.bash_code_path_execute],
                                            stdout=subprocess.PIPE,  # 把子进程的“标准输出（stdout）”重定向到一个管道（PIPE），让Python程序可以读取它，而不是直接打印到终端
                                            stderr=subprocess.PIPE,
                                            text=True)

        # 实时读取输出并打印
        stdout = []
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:  # 后者检查子进程是否还在运行，输出none表示子进程还在运行
                break
            print(f'[stdout] {output.strip()}')
            stdout.append(f'[stdout] {output.strip()}')

        stderr = []
        for _ in process.stderr.readlines():
            if 'EnvironmentNameNotFound' in _ or '\n' == _:
                pass
            else:
                print(f"[stderr] {_}", end='')
                stderr.append(_)

        if len(stdout) > 10:
            stdout = stdout[-10:]
        if len(stderr) > 10:
            stderr = stderr[-10:]

        stdout = '\n'.join(stdout)
        stderr = '\n'.join(stderr)

        process.communicate()

        executor_info = stdout + '\n' + stderr
        return executor_info
