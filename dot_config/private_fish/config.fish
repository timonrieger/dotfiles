# set -gx PATH /opt/homebrew/bin /opt/homebrew/sbin $PATH

if status is-interactive
    # Commands to run in interactive sessions can go here
    atuin init fish | source
end

# Aliasse
alias pn="pnpm"
alias mr="mise run"
alias web="code ~/code/projects/website/"
alias ds="docker ps -a --format 'table {{.ID}}\t{{.Status}}\t{{.Names}}\t{{.Ports}}'"
alias gc="git checkout"
alias ml="mise tasks ls --hidden"
alias curltime="curl -w \"@$HOME/.curl-format.txt\" -o /dev/null -s "

# uv
fish_add_path "/Users/timon/.local/bin"
eval (/opt/homebrew/bin/brew shellenv)
