import os
import vdf
import math
import winreg
from typing import List, Dict
from enum import IntFlag


class Utilities:
    @staticmethod
    def convert_size(size_bytes: int):
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"


class WorkshopData:
    def __init__(self, data: dict):
        self.data = data
        self.parse_data()

    def __bool__(self):
        return bool(self.data)

    def parse_data(self):
        if self.data:
            self.library = self.data["library"]

            workshop_data = self.data["AppWorkshop"]

            self.appid = workshop_data["appid"]
            self.path = os.path.join(self.library.path, "steamapps", "workshop", "content", self.appid)

            self.size_bytes = int(workshop_data["SizeOnDisk"])
            self.size = Utilities.convert_size(self.size_bytes)


class SteamGame:
    class AppState(IntFlag):
        StateInvalid = 0
        StateUninstalled = 1
        StateUpdateRequired = 2
        StateFullyInstalled = 4
        StateEncrypted = 8
        StateLocked = 16
        StateFilesMissing = 32
        StateAppRunning = 64
        StateFilesCorrupt = 128
        StateUpdateRunning = 256
        StateUpdatePaused = 512
        StateUpdateStarted = 1024
        StateUninstalling = 2048
        StateBackupRunning = 4096
        StateReconfiguring = 65536
        StateValidating = 131072
        StateAddingFiles = 262144
        StatePreallocating = 524288
        StateDownloading = 1048576
        StateStaging = 2097152
        StateCommitting = 4194304
        StateUpdateStopping = 8388608

    def __init__(self, data: dict):
        self.data = data
        self.parse_data()

    def __repr__(self):
        return f"<SteamGame : '{self.name}' : {self.size}>"

    def __lt__(self, other):
        return self.name < other

    def __gt__(self, other):
        return self.name > other

    def parse_data(self):
        self.library = self.data["library"]
        self.workshop_data = WorkshopData(self.data["workshop"])

        game_data = self.data["AppState"]

        self.appid = game_data["appid"]
        self.name = game_data["name"]
        self.state = self.AppState(int(game_data["StateFlags"]))
        self.path = os.path.join(self.library.path, "steamapps", "common", game_data["installdir"])

        self.size_bytes = int(game_data["SizeOnDisk"])
        self.size = Utilities.convert_size(self.size_bytes)


class SteamLibrary:
    def __init__(self, data: dict):
        self.data = data
        self.parse_data()

    def parse_data(self):
        self.games: List[SteamGame] = list()
        self.path = self.data["path"]

        manifests: List[Dict[str, os.PathLike]] = list()
        for appid in self.data["apps"]:
            game_manifest = os.path.join(self.path, "steamapps", f"appmanifest_{appid}.acf")
            workshop_manifest = os.path.join(self.path, "steamapps", "workshop", f"appworkshop_{appid}.acf")

            manifest_data = {
                "game": game_manifest,
                "workshop": workshop_manifest
            }

            manifests.append(manifest_data)

        for manifest in manifests:
            with open(manifest["game"]) as file:
                data = vdf.loads(file.read())

            try:
                with open(manifest["workshop"]) as file:
                    data["workshop"] = vdf.loads(file.read())
                    data["workshop"]["library"] = self

            except FileNotFoundError:
                data["workshop"] = None

            data["library"] = self
            self.games.append(SteamGame(data))

    @property
    def size_bytes(self):
        return sum([game.size_bytes for game in self.games])

    @property
    def size(self):
        return Utilities.convert_size(self.size_bytes)


class SteamParser:
    def __init__(self):
        self.steam_path = self.find_steam_path()
        self.steam_libraries = self.find_steam_libraries(self.steam_path)

    @property
    def all_games(self):
        game_list: List[SteamGame] = list()
        for library in self.steam_libraries:
            for game in library.games:
                game_list.append(game)

        game_list.sort()
        return game_list

    @property
    def size_bytes(self):
        sum_size = 0
        for library in self.steam_libraries:
            for game in library.games:
                sum_size += game.size_bytes
                if game.workshop_data:
                    sum_size += game.workshop_data.size_bytes

        return sum_size

    @property
    def size(self):
        return Utilities.convert_size(self.size_bytes)

    @staticmethod
    def find_steam_path():
        """Searches the Windows registry for a steam installation"""
        steam_path = None
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                handle = winreg.ConnectRegistry(None, hive)
                valve_key = winreg.OpenKey(handle, r"SOFTWARE\Valve\Steam")
                steam_path = winreg.QueryValueEx(valve_key, "SteamPath")[0]
                winreg.CloseKey(valve_key)
                
            except FileNotFoundError:
                continue

        return steam_path

    @staticmethod
    def find_steam_libraries(steam_path: os.PathLike):
        """Searches for steam library locations"""
        library_paths = list()
        with open(f"{steam_path}/steamapps/libraryfolders.vdf") as library_manifest:
            library_data = vdf.loads(library_manifest.read())

        for library in [i for i in library_data["libraryfolders"].values()][1:]:
            library_paths.append(SteamLibrary(library))

        return library_paths


# If script is being run standalone, start automatically (allows this file to be run, or to be imported from)
if __name__ == "__main__":
    # Instantiating a SteamParser
    steamparser = SteamParser()

    # Print out all games found
    for game in steamparser.all_games:
        print(game)

    # Print total size of all present steam games and workshop data
    print(f"Total Size: {steamparser.size}")
