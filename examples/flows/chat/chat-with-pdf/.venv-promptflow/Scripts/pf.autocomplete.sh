case $SHELL in
*/zsh)
   # Enable ZSH compatibility mode
   autoload bashcompinit && bashcompinit
   ;;
*/bash)
   ;;
*)
esac

eval "$(register-python-argcomplete pf)"
