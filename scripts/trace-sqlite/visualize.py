import datetime
import typing

import matplotlib.pyplot as plt


def read_timer_data() -> typing.Tuple[typing.List[datetime.datetime], typing.List[int], typing.List[int]]:
    tss, duration_mss, counts = [], [], []
    count = 0
    with open("./sqlite.timer.log") as f:
        for line in f.readlines():
            line = line.strip()
            # timestamp, 23 = len("2024-01-24 16:26:50,884")
            timestamp = datetime.datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
            # duraton_ms, 13 = len("duration_ms: ")
            duration_ms = int(line[line.index("duration_ms: ") + len("duration_ms: "):])
            # count
            count += 1
            tss.append(timestamp)
            duration_mss.append(duration_ms)
            counts.append(count)
    return tss, duration_mss, counts


def read_sqlite_lock_data() -> typing.List[datetime.datetime]:
    tss = []
    with open("./span.persisting.log") as f:
        for line in f.readlines():
            line = line.strip()
            timestamp = datetime.datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
            tss.append(timestamp)
    return tss


def main():
    timer_ts, timer_duration_ms, counts = read_timer_data()
    lock_ts = read_sqlite_lock_data()

    # Create two subplots
    fig, axs = plt.subplots(3)

    # Plot timestamp-duration on the first subplot
    axs[0].plot(timer_ts, timer_duration_ms)
    axs[0].set(xlabel="Timestamp", ylabel="Duration MS", title="Duration over time")

    axs[1].plot(timer_ts, counts)
    axs[1].set(xlabel="Timestamp", ylabel="Rows Count", title="#spans over time")

    # Plot timestamp existence on the second subplot
    # We use a list of ones to indicate the existence of a timestamp
    axs[2].plot(lock_ts, [1]*len(lock_ts), "o")
    axs[2].set(xlabel="Timestamp", ylabel="Existence", title="Existence of timestamps")
    axs[2].get_yaxis().set_visible(False)

    # Save the figure to a local file
    plt.savefig("figure.png")

    # Display the plots
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
