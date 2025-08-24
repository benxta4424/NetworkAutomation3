class Config:
    def __init__(self, filename):
        self.filename = filename
        self.contents = None

    def __enter__(self):
        with open(self.filename, "r") as file:
            self.contents = file.read().splitlines()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.contents = None

    def get_block(self, starts_from):
        result = []
        starts = False

        for l in self.contents:
            if l.startswith(starts_from):
                starts = True
                continue #sa inceapa de la urmatorul

            if starts and l != "!":
                result.append(l)


        return result

config_name = "conf.txt"
conf = Config(config_name)

with open(config_name, "w") as writer:
    writer.write("interface Ethernet0/3\nno ip address\nshutdown")

with Config(config_name) as line:
    block = line.get_block("interface Ethernet0/3")
    print(block)