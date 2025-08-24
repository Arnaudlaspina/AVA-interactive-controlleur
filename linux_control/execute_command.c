





















#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <sys/inotify.h>  
#include <fcntl.h>       

#define MAX_LINE_LENGTH 512
#define BASE_DIR "../shared_commands/"
#define LOCKFILE BASE_DIR "commands.lock"
#define CMD_FILE BASE_DIR "commands.txt"
#define LOG_FILE BASE_DIR "terminal.log"


int file_exists(const char *filename);
void create_lock();
void remove_lock();
void clear_file(const char *filename);
void executer_depuis_fichier();
void send_command_to_shell(const char *cmd);
void read_shell_output();


int shell_stdin[2];   
int shell_stdout[2];  

pid_t shell_pid;

int main() {
    setbuf(stdout, NULL); 

    
    struct stat st = {0};
    if (stat(BASE_DIR, &st) == -1) {
        if (mkdir(BASE_DIR, 0700) == 0)
            printf("Création du dossier %s\n", BASE_DIR);
        else {
            perror("Erreur création dossier");
            exit(1);
        }
    }

    
    FILE *test_log = fopen(LOG_FILE, "a");
    if (test_log) {
        fprintf(test_log, "=== Démarrage du programme (PID %d) ===\n", getpid());
        fclose(test_log);
        printf("Écriture test dans %s réussie\n", LOG_FILE);
    } else {
        perror("Erreur ouverture terminal.log pour test écriture");
    }

    
    if (pipe(shell_stdin) == -1 || pipe(shell_stdout) == -1) {
        perror("Erreur création pipes");
        exit(1);
    }

    
    shell_pid = fork();
    if (shell_pid == -1) {
        perror("Erreur fork");
        exit(1);
    }

    if (shell_pid == 0) {
        
        dup2(shell_stdin[0], STDIN_FILENO);   
        dup2(shell_stdout[1], STDOUT_FILENO); 
        dup2(shell_stdout[1], STDERR_FILENO); 

        close(shell_stdin[1]);
        close(shell_stdout[0]);

        execl("/bin/bash", "bash", "--noprofile", "--norc", NULL);
        perror("Erreur exec bash");
        exit(1);
    }

    
    close(shell_stdin[0]);
    close(shell_stdout[1]);

    printf("Shell forké avec PID: %d\n", shell_pid);

    
    int fd_inotify = inotify_init1(IN_NONBLOCK);
    if (fd_inotify < 0) {
        perror("inotify_init");
        exit(1);
    }

    
    int wd = inotify_add_watch(fd_inotify, BASE_DIR, IN_CLOSE_WRITE);
    if (wd < 0) {
        perror("inotify_add_watch");
        exit(1);
    }

    printf("En attente d'écriture dans %scommands.txt\n", BASE_DIR);

    char buffer[4096];

    while (1) {
        
        ssize_t length = read(fd_inotify, buffer, sizeof(buffer));
        if (length < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                
                read_shell_output();
                usleep(1000); 
                continue;
            } else {
                perror("read inotify");
                break;
            }
        }

        ssize_t i = 0;
        while (i < length) {
            struct inotify_event *event = (struct inotify_event *)&buffer[i];

            if ((event->mask & IN_CLOSE_WRITE) && strcmp(event->name, "commands.txt") == 0) {
                printf("Modification détectée sur commands.txt, lecture des commandes...\n");
                executer_depuis_fichier();
                read_shell_output();
            }

            i += sizeof(struct inotify_event) + event->len;
        }
    }

    close(fd_inotify);

    return 0;
}

int file_exists(const char *filename) {
    struct stat buffer;
    return (stat(filename, &buffer) == 0);
}

void create_lock() {
    FILE *f = fopen(LOCKFILE, "w");
    if (f) {
        fprintf(f, "locked");
        fclose(f);
    }
}

void remove_lock() {
    remove(LOCKFILE);
}

void clear_file(const char *filename) {
    FILE *f = fopen(filename, "w");
    if (f) fclose(f);
}

void send_command_to_shell(const char *cmd) {
    dprintf(shell_stdin[1], "%s\n", cmd);
    fsync(shell_stdin[1]);
}

void read_shell_output() {
    char buffer[256];
    ssize_t n;

    FILE *log_fp = fopen(LOG_FILE, "a");
    if (!log_fp) {
        perror("Erreur ouverture terminal.log");
        return;
    }

    
    fcntl(shell_stdout[0], F_SETFL, O_NONBLOCK);

    int data_read = 0;
    while ((n = read(shell_stdout[0], buffer, sizeof(buffer) - 1)) > 0) {
        data_read = 1;
        buffer[n] = '\0';

        
        printf("[Shell output] \n%s", buffer);

        
        if (fputs(buffer, log_fp) == EOF) {
            perror("Erreur écriture dans terminal.log");
        }
        fflush(log_fp);
    }

    if (n == -1 && errno != EAGAIN && errno != EWOULDBLOCK) {
        perror("Erreur lecture shell stdout");
    }

    fclose(log_fp);
}

void executer_depuis_fichier() {
    
    while (!file_exists(LOCKFILE)) {
        usleep(1000);
    }

    
    remove_lock();

    FILE *file = fopen(CMD_FILE, "r");
    if (!file) {
        perror("Erreur ouverture fichier commands.txt");
        return;
    }

    char line[MAX_LINE_LENGTH];
    #define MAX_COMMANDS 100
    char *commands[MAX_COMMANDS];
    int count = 0;

    while (fgets(line, sizeof(line), file)) {
        line[strcspn(line, "\r\n")] = 0;
        if (strlen(line) > 0) {
            commands[count++] = strdup(line);
            if (count >= MAX_COMMANDS) break;
        }
    }

    fclose(file);

    printf("Commandes reçues (%d):\n", count);
    for (int i = 0; i < count; i++) {
    	printf(" → %s\n", commands[i]);
    	send_command_to_shell(commands[i]);
    	usleep(1000);
    	free(commands[i]);
    }

    clear_file(CMD_FILE);
}





