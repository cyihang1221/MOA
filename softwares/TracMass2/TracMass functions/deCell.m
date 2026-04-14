function x=deCell(x)
%Magnus Åberg

if numel(x) == 1,
    while(iscell(x))
        x = x{1};
    end
else
    if iscell(x),
        while iscell( x(1) )
            x = [ x{:} ];
        end
    end
end