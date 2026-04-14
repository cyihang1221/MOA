function name = filename(filestr)
% name = filename(filestr)
% returns the file name without path or extension.
%
% Magnus Åberg
if ischar(filestr)
    [foo,name] = fileparts(filestr);
elseif isstruct(filestr)
    N = numel(filestr);
    name = cell(N,1);
    for i = 1:N,
        [foo, nm] = fileparts(filestr(i).name);
        name{i} = nm;
    end
end
