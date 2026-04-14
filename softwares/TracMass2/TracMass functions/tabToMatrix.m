function [X,id1,id2] = tabToMatrix(tab,rowField,colField,valueField)
%[X,id1,id2] = tabToMatrix(tab,rowField,colField,valueField)
% "X(rowField,colField) = tab.(valueField)"

%by: Magnus Åberg

id1 = unique(tab.(rowField));
id2 = unique(tab.(colField));

row(id1) = 1:numel(id1);

nRow = numel(id1);
nCol = numel(id2);

X = nan(nRow,nCol);
for iCol = 1:nCol
    mask = tab.(colField) == id2(iCol); % get positions for column iCol
    val = tab.(valueField)(mask); % get values
    ir = tab.(rowField)(mask); % get rows 
    
    assert(numel(ir)==numel(unique(ir)))% all unique
    assert(all(floor(ir)==ir)); % integers

    %X(ir,iCol) = val; % old buggy version
    X( row(ir), iCol ) = val; % new better version which doesn't add a lot of zeros?
end