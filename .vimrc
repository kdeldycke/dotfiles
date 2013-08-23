set nocompatible

" Pathogen
call pathogen#infect()
call pathogen#helptags()
 
set statusline=%<\ %n:%f\ %m%r%y%=%-35.(line:\ %l\ of\ %L,\ col:\ %c%V\ (%P)%)
filetype plugin indent on
 
syntax on
set number
set mouse=a
set mousehide

set hlsearch
set showmatch
set incsearch
set ignorecase
set wrap
set autoindent
set history=1000
set cursorline

set expandtab
set shiftwidth=4
set tabstop=4
set softtabstop=4
set backspace=2

set background=dark
colorscheme solarized
